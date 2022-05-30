# from circuitpy_mcu.mcu import Mcu
# from circuitpy_mcu.display import LCD_20x4
import adafruit_requests
import ssl
import socketpool
import wifi
import neopixel
import board
from microcontroller import watchdog
from watchdog import WatchDogMode, WatchDogTimeout

# import dualbank
import time
import os

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

class Bootloader():

    def __init__(self, watchdog_timeout=20):

            # def enable_watchdog(self, timeout=20):
        # Setup a watchdog to reset the device if it stops responding.
        self.watchdog = watchdog
        self.watchdog.timeout=watchdog_timeout #seconds
        # watchdog.mode = WatchDogMode.RESET # This does a hard reset
        self.watchdog.mode = WatchDogMode.RAISE # This prints a message then does a soft reset
        self.watchdog.feed()
        print(f'Watchdog enabled with timeout = {self.watchdog.timeout}s')

        # Setup Neopixel, helpful to indicate status 
        # self.pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, auto_write=True)
        # self.pixel.RED      = 0xff0000
        # self.pixel.GREEN    = 0x00ff00
        # self.pixel.BLUE     = 0x0000ff
        # self.pixel.MAGENTA  = 0xff00ff
        # self.pixel.YELLOW   = 0xffff00
        # self.pixel.CYAN     = 0x00ffff
        # pixel_brightness = 0.1
        # self.pixel.brightness = pixel_brightness
        # self.pixel[0] = self.pixel.GREEN

        self.requests = None


    def writable_check(self):
        try:
            with open('write_test.txt', 'w') as f:
                f.write('test')
                # print('write success')
            os.remove('write_test.txt')
            return True
            
        except Exception as e:
            print(e)
            # print('write failed')
            return False

    def wifi_scan(self):
        print('\nScanning for nearby WiFi networks...')
        self.networks = []
        for network in wifi.radio.start_scanning_networks():
            self.networks.append(network)
        wifi.radio.stop_scanning_networks()
        self.networks = sorted(self.networks, key=lambda net: net.rssi, reverse=True)
        for network in self.networks:
            print(f'ssid: {network.ssid}\t rssi:{network.rssi}')


    def wifi_connect(self):
        ### WiFi ###

        # Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
        # "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
        # source control.

        i=0
        ssid = secrets["ssid"]
        password = secrets["password"]
        try:
            # Try to detect strongest wifi
            # If it is in the known networks list, use it
            self.wifi_scan()
            strongest_ssid = self.networks[0].ssid
            if strongest_ssid in secrets["networks"]:
                ssid = strongest_ssid
                password = secrets["networks"][ssid]
                print('Using strongest wifi network')
        except Exception as e:
            print(e)

        while True:
            try:
                print(f'Wifi: {ssid}')
                wifi.radio.connect(ssid, password)
                print("Wifi Connected")
                # self.pixel[0] = self.pixel.CYAN
                self.wifi_connected = True
                self.watchdog.feed()
                break
            except ConnectionError as e:
                print(e)
                print(f"{ssid} connection failed")
                network_list = list(secrets['networks'])
                ssid = network_list[i]
                password = secrets["networks"][network_list[i]]
                time.sleep(1)
                i +=1
                if i >= len(secrets['networks']):
                    i=0

        self.pool = socketpool.SocketPool(wifi.radio)
        self.requests = adafruit_requests.Session(self.pool, ssl.create_default_context())


    def mkdir_parents(self, path):
        dirs = path.split('/')[1:-1]
        for i in range(len(dirs)):
            d = ''
            for n in range(i+1):
                d+=f'/{dirs[n]}'
            try:
                os.mkdir(d)  
                print(f'created dir {d}')
            except Exception as e:
                if e.args[0] == 30:
                    print('Error, Read Only Filesystem, please configure boot.py to remount storage appropriately')
                if e.args[0] == 17:
                    # Directory already exists
                    pass
                else:
                    print(f'Trying to mkdir {d}')
                    print(e)

    def get_ota_list(self, url):
        
        if not self.writable_check:
            raise Exception('Error, Read Only Filesystem, please configure boot.py to remount storage appropriately')

        if not self.requests:
            self.wifi_connect()

        try:
            print(f'trying to fetch ota files defined in {url}')
            response = self.requests.get(url)
            ota_list = response.json()

            for path, list_url in ota_list.items():
                self.watchdog.feed()
                self.mkdir_parents(path)
                print(f'saving {list_url} to {path}')
                file = self.requests.get(list_url).content
                with open(path, 'w') as f:
                    f.write(file)
            
            return True
                # print(f'reading {path}')
                # with open(path, 'r') as f:
                #     line = f.readline()
                #     while line != '':
                #         print(line)
                #         line = f.readline()

        except Exception as e:
            print(e)
            print(f'Could not get {url}')
            raise

# while True:
#     mcu.watchdog.feed()
#     print('receiving')
#     mcu.aio_receive()
#     mcu.io.get(f'{AIO_GROUP}.ota')

#     if mcu.ota_requested:
#         get_ota_list(OTA_LIST_URL)
#         mcu.ota_requested = False

#     print('importing')


#     print('sleeping 3')
#     time.sleep(3)

# pool = socketpool.SocketPool(wifi.radio)
# requests = adafruit_requests.Session(pool, ssl.create_default_context())


# url = f'https://downloads.circuitpython.org/bin/adafruit_feather_esp32s2/en_GB/adafruit-circuitpython-adafruit_feather_esp32s2-en_GB-7.2.5.bin'
# response = requests.get(url)

# chunk_size = 1024
# offset=0
# for chunk in response.iter_content(chunk_size):
#     print(f'offset = {offset}')
#     dualbank.flash(chunk, offset=offset)
#     offset += chunk_size