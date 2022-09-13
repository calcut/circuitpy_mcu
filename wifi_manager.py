# System and timing
import time
import microcontroller
import adafruit_logging as logging
import traceback

# Networking
import wifi
import ssl
import socketpool
import adafruit_requests
import ipaddress

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

#pinging too fast can cause a hardfault https://github.com/adafruit/circuitpython/issues/5980
MAX_PING_RATE = 0.5 #seconds, 

class Wifi_manager():
    def __init__(self, loghandler=None, offline_retry_connection=60, max_errors=3):


        # Set up logging
        self.log = logging.getLogger('wifi')
        if loghandler:
            self.log.addHandler(loghandler)

        self.connected = False

        self.offline_mode = False
        self.timer_offline = time.monotonic()

        self.connection_error_count = 0
        self.max_errors = max_errors #How many ConnectionErrors before going into offline mode
        # self.offline_retry_connection = False #hard reset after max_errors exceeded
        self.offline_retry_connection = offline_retry_connection #seconds

        self.pool = socketpool.SocketPool(wifi.radio)
        self.requests = adafruit_requests.Session(self.pool, ssl.create_default_context())
        self.timer_ping = 0


    def wifi_scan(self):
        try:
            self.log.info('Scanning for nearby WiFi networks...')
            self.networks = []
            for network in wifi.radio.start_scanning_networks():
                self.networks.append(network)
            wifi.radio.stop_scanning_networks()
            self.networks = sorted(self.networks, key=lambda net: net.rssi, reverse=True)
            for network in self.networks:
                self.log.debug(f'ssid: {network.ssid}\t rssi:{network.rssi}')
        except Exception as e:
            self.handle_exception(e)


    def connectivity_check(self, host='dns.google', port=443):
        try:
            if self.offline_mode:
                self.log.debug(f"connectivity_check() == False because {self.offline_mode=}")
                if self.offline_retry_connection:
                    # See if it it time to try getting online again
                    if time.monotonic() - self.timer_offline > self.offline_retry_connection:
                        self.offline_mode = False
                        self.log.debug(f'Setting offline_mode = False')

                return False

            if not self.connected:
                raise ConnectionError(f"{self.connected=}")

            ip_str = self.pool.getaddrinfo(host, port)[0][4][0]
            ping_addr = ipaddress.ip_address(ip_str)

            i = 0
            while True:
                if (time.monotonic() - self.timer_ping) > MAX_PING_RATE:
                    i +=1
                    ping = wifi.radio.ping(ping_addr, timeout=1)
                    self.timer_ping = time.monotonic()
                    if ping:
                        break
                    if i >= 5:
                        break
                    time.sleep(MAX_PING_RATE)

            if i > 1:
                self.log.debug(f'{i=}, {ping} took several attempts to ping')
            if not ping:
                self.connected = False
                raise ConnectionError(f"No ping response received from {host} {ip_str}")
            else:
                self.log.debug(f"{ping=}")
                return True

        except Exception as e:
            self.handle_exception(e)
            return False


    def connect(self, attempts=4, scan=True):
        ### WiFi ###

        # Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
        # "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
        # source control.
        if self.offline_mode:
            self.log.info(f'Cancelling wifi connection, {self.offline_mode=}')
            return False

        try:
            # This toggle is helpful when dealing with reconnections
            # Otherwise the wifi.radio.connect() function doesn't produce the expected exceptions.
            wifi.radio.enabled = False
            wifi.radio.enabled = True
            i=0
            ssid = secrets["ssid"]
            password = secrets["password"]
            
            if scan:
                # Try to detect strongest wifi
                # If it is in the known networks list, use it
                self.wifi_scan()
                strongest_ssid = self.networks[0].ssid
                if strongest_ssid in secrets["networks"]:
                    ssid = strongest_ssid
                    password = secrets["networks"][ssid]
                    self.log.info('Using strongest wifi network')


            attempt=0
            while True:
                attempt += 1
                if attempt > attempts:
                    self.log.warning(f'Wifi not connected after {attempts} attempts')
                    self.connected = False
                    return False
                try:
                    self.log.info(f'{ssid}')
                    self.display(f'Wifi: {ssid}')
                    wifi.radio.connect(ssid, password)
                    self.connected = True
                    break
                except ConnectionError as e:
                    self.watchdog_feed()
                    self.log.warning(f"{ssid} connection failed on attempt {attempt}/{attempts}: {e}")
                    # self.display_text("Connection Failed")
                    i +=1
                    if i >= len(secrets['networks']):
                        i=0
                    network_list = list(secrets['networks'])
                    ssid = network_list[i]
                    password = secrets["networks"][network_list[i]]

          
            self.pool = socketpool.SocketPool(wifi.radio)
            self.requests = adafruit_requests.Session(self.pool, ssl.create_default_context())
            self.connectivity_check()
            self.log.info("Connected")
            self.display("Wifi Connected")
            self.watchdog_feed()

            return True  

        except Exception as e:
            self.handle_exception(e)


    def handle_exception(self, e):
        cl = e.__class__

        if cl == OSError:
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.critical(f"Wifi OSError, Hard resetting now")
            microcontroller.reset()

        if cl == ConnectionError:
            if self.offline_mode:
                self.log.warning(f"ConnectionError: {e}, ignoring becuase {self.offline_mode=}")
            else:
                self.connection_error_count +=1
                self.log.warning(f"ConnectionError: {e}, {self.connection_error_count=}/{self.max_errors}")
                if self.connection_error_count >= self.max_errors:
                    if self.offline_retry_connection == False:
                        self.log.warning(f"Hard resetting")
                        microcontroller.reset()
                    self.log.warning(f"Entering offline mode")
                    self.offline_mode=True
                    self.timer_offline = time.monotonic()
                    self.connection_error_count = 0
                    return
                self.connect()      

        else:
            # formats an exception to print to log as an error,
            # includues the traceback (to show code line number)
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.warning(f'No handler for this exception')
            # raise

    def display(self, message):
        # Special log command with custom level, to request sending to attached display
        self.log.log(level=25, msg=message)

    def watchdog_feed(self):
        try:
            microcontroller.watchdog.feed()
        except ValueError:
            # Happens if watchdog timer hasn't been started
            pass