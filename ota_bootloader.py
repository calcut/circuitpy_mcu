# from circuitpy_mcu.mcu import Mcu
import adafruit_requests
import ssl
import socketpool
import wifi
import neopixel
import board
import digitalio
import busio
import microcontroller
from watchdog import WatchDogMode, WatchDogTimeout
import traceback
import supervisor

# import dualbank
import time
import os

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

def enable_watchdog(timeout=20):
    # Setup a watchdog to reset the device if it stops responding.
    watchdog = microcontroller.watchdog
    watchdog.timeout=timeout #seconds
    # watchdog.mode = WatchDogMode.RESET # This does a hard reset
    watchdog.mode = WatchDogMode.RAISE # This raises an exception
    watchdog.feed()
    print(f'Watchdog enabled with timeout = {timeout}s')


def reset(exception=None):
    if exception:
        detail = traceback.format_exception(exception)[0]
        print(detail)
        try:
            with open('log_exception.txt', 'a') as f:
                f.write(detail)
                print('logged exception to /log_exception.txt')

        except Exception as e:
                print(f'Unable to save exception details, {e}')

    try:
        if supervisor.runtime.usb_connected:
            print('USB connected, performing soft reset in 15s')
            time.sleep(15)
            supervisor.reload()
        else:
            print('Performing a hard reset')
            microcontroller.reset()
    except WatchDogTimeout:
        print('watchdog timeout during reset, performing hard reset')
        microcontroller.reset()

class Bootloader():

    def __init__(self, url):
        enable_watchdog(timeout=120)

        i2c = None
        i2c_power = None

        try:
            from sparkfun_serlcd import Sparkfun_SerLCD_I2C


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
            self.led = digitalio.DigitalInOut(board.LED)
            self.led.direction = digitalio.Direction.OUTPUT
            self.led.value = False
        except Exception as e:
            print(f'heartbeat LED error: {e}')

        try:
            self.get_ota_list(url)
            if i2c_power:
                i2c_power.deinit()
            if i2c:
                i2c.deinit()

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
            self.display.set_cursor(0,row)
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
                self.display_text(f'Wifi: {ssid}', row=2, clear=False)
                wifi.radio.connect(ssid, password)
                print("Wifi Connected")
                self.wifi_connected = True
                microcontroller.watchdog.feed()
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
                print('\nSkipping OTA Update. Read Only Filesystem')
                self.display_text(f'Skipping OTA Update', row=0, clear=False)
                print('please configure boot.py to remount storage appropriately\n')
                time.sleep(1)
                return False

            uid = microcontroller.cpu.uid
            id = f'{uid[-2]:02x}{uid[-1]:02x}'

            self.display_text('Over-the-Air Update')
            self.display_text(f'id: {id}', row=1, clear=False)
            self.wifi_connect()

            print(f'trying to fetch ota files defined in {url}, with id={id}')
            self.display_text(f'ota_list.py id={id}')
            response = self.requests.get(url)
            ota_list = response.json()[id]
            print(ota_list)

            for path, item_url in ota_list.items():
                microcontroller.watchdog.feed()
                if self.led:
                    self.led.value = not self.led.value
                self.mkdir_parents(path)
                print(f'saving {item_url} to {path}')
                url_list = item_url.split('/')
                self.display_text(f'{url_list[-1]}', row=0, clear=True)
                self.display_text(f'{url_list[-2]}', row=1, clear=False)
                self.display_text(f'{url_list[-3]}', row=2, clear=False)
                time.sleep(0.5)
                file = self.requests.get(item_url).content
                with open(path, 'w') as f:
                    f.write(file)

            self.display_text(f'OTA Success', row=0, clear=True)
            time.sleep(1)
            return True

        except Exception as e:
            print(e)
            print(f'Could not get {url}, with id={id}')
            try:
                self.display_text(f'OTA Failed id={id}')
                url_list = url.split('/')
                self.display_text(f'{url_list[-1]}', row=1, clear=False)
                self.display_text(f'{url_list[-2]}', row=2, clear=False)
                self.display_text(f'{url_list[-3]}', row=3, clear=False)
                time.sleep(10)
            except:
                pass
            # don't raise - want to continue to boot if no wifi is available.
            # raise
