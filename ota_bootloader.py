# from circuitpy_mcu.mcu import Mcu
import adafruit_requests
import ssl
import socketpool
import wifi
import neopixel
# import board
import microcontroller
from watchdog import WatchDogMode, WatchDogTimeout
import traceback

# import dualbank
import time
import os

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


class Bootloader():

    def __init__(self, url, watchdog_timeout=20):

        # Setup a watchdog to reset the device if it stops responding.
        self.watchdog = microcontroller.watchdog
        self.watchdog.timeout=watchdog_timeout #seconds
        # watchdog.mode = WatchDogMode.RESET # This does a hard reset
        self.watchdog.mode = WatchDogMode.RAISE # This prints a message then does a soft reset
        self.watchdog.feed()
        print(f'Watchdog enabled with timeout = {self.watchdog.timeout}s')

        try:
            from sparkfun_serlcd import Sparkfun_SerLCD_I2C
            import digitalio
            import board
            import busio

            # Ensure I2C is powered on, regardless of board rev
            i2c_power = digitalio.DigitalInOut(board.I2C_POWER)
            i2c_power.switch_to_input()
            time.sleep(0.01)  # wait for default value to settle
            rest_level = i2c_power.value
            i2c_power.switch_to_output(value=(not rest_level))
            time.sleep(1.5) # Display sometimes needs >1s!

            i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)

            self.display = Sparkfun_SerLCD_I2C(i2c)
            self.display.set_fast_backlight_rgb(255, 255, 255)

        except Exception as e:
            print(e)
            print('Error setting up 20x4 i2c Display')
            self.display = None

        try:
            self.get_ota_list(url) 

        except WatchDogTimeout:
            print('Code Stopped by WatchDog Timeout during OTA update!')
            print('Performing hard reset in 15s')
            time.sleep(15)
            microcontroller.reset()

        except Exception as e:
            print(f'Code stopped by unhandled exception:')
            print(traceback.format_exception(None, e, e.__traceback__))
            print('Performing a hard reset in 15s')
            time.sleep(15) #Make sure this is shorter than watchdog timeout
            microcontroller.reset()

    def display_text(self, text, row=0, clear=True):
        if self.display:
            if clear:
                self.display.clear()
            self.set_cursor(0,row)
            self.display.write(text)

    def i2c_power_on(self):
        # Due to board rev B/C differences, need to read the initial state
        # https://learn.adafruit.com/adafruit-esp32-s2-feather/i2c-power-management
        self.i2c_power = digitalio.DigitalInOut(board.I2C_POWER)
        self.i2c_power.switch_to_input()
        time.sleep(0.01)  # wait for default value to settle
        rest_level = self.i2c_power.value

        self.i2c_power.switch_to_output(value=(not rest_level))
        time.sleep(1)

    def writable_check(self):
        try:
            with open('write_test.txt', 'w') as f:
                f.write('test')
            os.remove('write_test.txt')
            return True
            
        except Exception as e:
            # print(e)
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
                self.display_text(f'Wifi: {ssid}', row=1, clear=False)
                wifi.radio.connect(ssid, password)
                print("Wifi Connected")
                self.display_text(f'Wifi Connected', row=2, clear=False)
                # self.pixel[0] = self.pixel.CYAN
                self.wifi_connected = True
                self.watchdog.feed()
                break
            except ConnectionError as e:
                print(e)
                print(f"{ssid} connection failed")
                self.display_text(f'Connection Failed', row=2, clear=False)
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
        
        try:
            if not self.writable_check():
                print('\nOTA Update Failed. Read Only Filesystem')
                print('please configure boot.py to remount storage appropriately\n')
                time.sleep(3)
                return False

            self.display_text('Over-the-Air Update')
            self.wifi_connect()

            print(f'trying to fetch ota files defined in {url}')
            self.display_text(f'{url}')
            response = self.requests.get(url)
            ota_list = response.json()

            for path, list_url in ota_list.items():
                self.watchdog.feed()
                self.mkdir_parents(path)
                print(f'saving {list_url} to {path}')
                self.display.show_text(f'{path}')
                file = self.requests.get(list_url).content
                with open(path, 'w') as f:
                    f.write(file)
            
            return True

        except Exception as e:
            print(e)
            print(f'Could not get {url}')
            raise
