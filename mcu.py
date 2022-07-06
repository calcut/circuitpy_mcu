# A helper library targeted at using Adafruit ESP32S2 Feather in a datalogger /
# iot controller.
# Essentially this just abstracts some common code to have a simpler top level.

# System and timing
import time
import rtc
import microcontroller
import supervisor
import gc
import usb_cdc
import adafruit_logging as logging
import traceback
import os
# from adafruit_logging import LoggingHandler

# On-board hardware
import board
import neopixel
import busio
import digitalio
import analogio
import adafruit_sdcard
import storage

# Networking
import wifi
import ssl
import socketpool
import adafruit_requests

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

try:
    # Import Known display types
    from circuitpy_mcu.display import LCD_16x2, LCD_20x4
except:
    pass


__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

class Mcu():
    def __init__(self, i2c_freq=50000, i2c_lookup=None, uart_baud=None):

        uid = microcontroller.cpu.uid
        self.id = f'{uid[-2]:02x}{uid[-1]:02x}'

        # Initialise some key variables
        self.wifi_connected = False
        self.aio_log_feed = None
        self.data = {} # A dict to store the outgoing values of data
        self.logdata = None # A str to accumulate non urgent logs to send to AIO periodically
        self.booting = False # a flag to indicate boot log messages should be recorded
        self.timer_publish = time.monotonic()
        self.timer_throttled = time.monotonic()
        self.sdcard = None
        self.display = None
        self.serial_buffer = ''

        # Real Time Clock in ESP32-S2 can be used to track timestamps
        self.rtc = rtc.RTC()

        # Set up logging
        # See McuLogHandler for details
        self.log = logging.getLogger('mcu')
        self.loghandler = McuLogHandler(self)
        self.log.addHandler(self.loghandler)
        self.log.level = logging.INFO

        # Pull the I2C power pin low to enable I2C power
        self.log.info('Powering up I2C bus')
        self.i2c_power = digitalio.DigitalInOut(board.I2C_POWER)
        self.i2c_power_on()
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=i2c_freq)

        if uart_baud:
            self.uart = busio.UART(board.TX, board.RX, baudrate=uart_baud)
        else:
            self.uart = None

        # Setup Neopixel, helpful to indicate status 
        self.pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, auto_write=True)
        self.pixel.RED      = 0xff0000
        self.pixel.GREEN    = 0x00ff00
        self.pixel.BLUE     = 0x0000ff
        self.pixel.MAGENTA  = 0xff00ff
        self.pixel.YELLOW   = 0xffff00
        self.pixel.CYAN     = 0x00ffff
        pixel_brightness = 0.1
        self.pixel.brightness = pixel_brightness
        self.pixel[0] = self.pixel.GREEN

        self.led = digitalio.DigitalInOut(board.LED)
        self.led.direction = digitalio.Direction.OUTPUT
        self.led.value = False


    def log_exception(self, e):
        # formats an exception to print to log as an error,
        # includues the traceback (to show code line number)
        self.log.error(traceback.format_exception(None, e, e.__traceback__))

    def i2c_power_on(self):
        # Due to board rev B/C differences, need to read the initial state
        # https://learn.adafruit.com/adafruit-esp32-s2-feather/i2c-power-management
        self.i2c_power.switch_to_input()
        time.sleep(0.01)  # wait for default value to settle
        rest_level = self.i2c_power.value

        self.i2c_power.switch_to_output(value=(not rest_level))
        time.sleep(1.5) # Sometimes even 1s is not enough for e.g. i2c displays. Worse in the heat?

    def i2c_power_off(self):
        self.i2c_power.switch_to_input()
        time.sleep(1)

    def i2c_power_off(self):
        self.i2c_power.switch_to_output(value=True)
        time.sleep(1)

    def i2c_identify(self, i2c_lookup=None):
        while not self.i2c.try_lock():  pass

        if i2c_lookup:
            self.log.info(f'\nChecking if expected I2C devices are present:')
            
            lookup_result = i2c_lookup.copy()
            devs_present = []
            for addr in self.i2c.scan():
                devs_present.append(f'0x{addr:0{2}X}')

            for addr_hex in i2c_lookup:
                if addr_hex in devs_present:
                    lookup_result[addr_hex] = True
                    devs_present.remove(addr_hex)
                else:
                    lookup_result[addr_hex] = False
            
                self.log.info(f'{addr_hex} : {i2c_lookup[addr_hex]} = {lookup_result[addr_hex]}')
                
            if len(devs_present) > 0:
                self.log.info(f'Unknown devices found: {devs_present}')

        else:
            for device_address in self.i2c.scan():
                addr_hex = f'0x{device_address:0{2}X}'
                self.log.info(f'{addr_hex}')
            lookup_result = None

        self.i2c.unlock()
        return lookup_result

    def wifi_scan(self):
        self.log.info('\nScanning for nearby WiFi networks...')
        self.networks = []
        for network in wifi.radio.start_scanning_networks():
            self.networks.append(network)
        wifi.radio.stop_scanning_networks()
        self.networks = sorted(self.networks, key=lambda net: net.rssi, reverse=True)
        for network in self.networks:
            self.log.info(f'ssid: {network.ssid}\t rssi:{network.rssi}')


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
                self.log.info('Using strongest wifi network')
        except Exception as e:
            self.log_exception(e)

        while True:
            try:
                self.log.info(f'Wifi: {ssid}')
                self.display_text(f'Wifi: {ssid}')
                wifi.radio.connect(ssid, password)
                self.log.info("Wifi Connected")
                self.display_text("Wifi Connected")
                self.pixel[0] = self.pixel.CYAN
                self.wifi_connected = True
                microcontroller.watchdog.feed()
                break
            except ConnectionError as e:
                self.log_exception(e)
                self.log.error(f"{ssid} connection failed")
                self.display_text("Connection Failed")
                network_list = list(secrets['networks'])
                ssid = network_list[i]
                password = secrets["networks"][network_list[i]]
                time.sleep(1)
                i +=1
                if i >= len(secrets['networks']):
                    i=0

        self.pool = socketpool.SocketPool(wifi.radio)
        self.requests = adafruit_requests.Session(self.pool, ssl.create_default_context())
                

    def get_timestamp(self):
        t = self.rtc.datetime
        string = f'{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} {t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}'
        return string

    def attach_display(self, display_object):
        self.display = display_object

    def attach_sdcard(self, cs_pin=board.D10):
        
        try:
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
            cs = digitalio.DigitalInOut(cs_pin)
            self.sdcard = adafruit_sdcard.SDCard(spi, cs)
            vfs = storage.VfsFat(self.sdcard)
            storage.mount(vfs, "/sd")
            self.display_text('SD Card Mounted')
            self.log.info('SD Card Mounted')
        except OSError:
            self.sdcard = None
            self.log.warning('SD Card not mounted')
        except Exception as e:
            self.sdcard = None
            self.log_exception(e)

    def delete_archive(self, archive_dir='/sd/archive'):
        try:
            list = os.listdir(archive_dir)
            for f in list:
                filepath = f'{archive_dir}/{f}'
                os.remove(filepath)
                self.log.info(f'Deleted {filepath}')
        except:
            self.log.warning(f'{dir} directory not found')
            return


    def archive_file(self, file, dir='/sd', archive_dir='/sd/archive'):

        try:
            list = os.listdir(dir)
        except:
            self.log.warning(f'{dir} directory not found')
            return

        if not file in list:
            self.log.warning(f'{dir}/{file} file not found for archival')
            return

        try:
            os.mkdir(archive_dir)
        except:
            # typically archive_dir already exists
            pass

        n=1
        filepath = f'{dir}/{file}'
        file = file[:-4] #Remove the extension, assumes 3 char extension
        newfile = f'{file}_{n:02d}.txt'

        while True:
            if newfile in os.listdir(archive_dir):
                n+=1
                newfile = f'{file}_{n:02d}.txt'
            else:
                break

        newpath = f'{archive_dir}/{newfile}'

        with open(filepath, 'r') as f:
            lines = f.readlines()
            self.log.info(f'---Last 10 lines of previous log {filepath}---')
            for l in lines[-10:]:
                self.log.info(l[:-1])
            self.log.info('--End of Previous log---')

        os.rename(filepath, newpath)
        self.log.info(f'{filepath} moved to {newpath}')

    def display_text(self, text):
        if self.display:
            if isinstance(self.display, LCD_16x2):
                self.display.clear()
                self.display.write(text)
            elif isinstance(self.display, LCD_20x4):
                self.display.clear()
                self.display.write(text)
            else:
                self.log.error("Unknown Display")

    def writable_check(self):
        # For testing if CIRCUITPY drive is writable by circuitpython
        try:
            with open('write_test.txt', 'w') as f:
                f.write('test')
            os.remove('write_test.txt')
            return True
            
        except Exception as e:
            # print(e)
            return False

    def read_serial(self, send_to=None):
        # This is likely broken, it was intended to be used with asyncio
        serial = usb_cdc.console
        text = ''
        available = serial.in_waiting
        while available:
            raw = serial.read(available)
            text = raw.decode("utf-8")
            print(text, end='')
            available = serial.in_waiting

        # Sort out line endings
        if text.endswith("\r"):
            text = text[:-1]+"\n"
        if text.endswith("\r\n"):
            text = text[:-2]+"\n"

        if "\r" in text:
            self.log.debug(f'carriage return \r found in {bytearray(text)}')

        self.serial_buffer += text
        if self.serial_buffer.endswith("\n"):
            input_line = self.serial_buffer[:-1]
            # clear buffer
            self.serial_buffer = ""
            # handle input
            if send_to:
                # Call the funciton provided with input_line as argument
                send_to(input_line)
            else:
                self.log.debug(f'you typed: {input_line}')
                return input_line
    
    def get_serial_line(self, valid_inputs=None):
        
        while True:
            line = None
            while not line:
                microcontroller.watchdog.feed()
                line = self.read_serial()

            if valid_inputs:
                if not line in valid_inputs:
                    print(f'invalid input: {line}')
                    continue
            
            return line

    def ota_reboot(self):
        if self.writable_check():
            self.log.warning('OTA update requested, resetting')
            time.sleep(1)
            microcontroller.reset()
        else:
            self.log.warning('OTA update requested, but CIRCUITPY not writable, skipping')

class McuLogHandler(logging.Handler):

    def __init__(self, mcu_device):
        self.aio = None # This can be passed later after aio connection is established
        self.device = mcu_device
        self.boot_time = time.monotonic()

    def _emit(self, level, msg):
        """Generate the message and write it to the AIO Feed.

        :param level: The level at which to log
        :param msg: The core message

        """

        if level == logging.INFO:

            # This is a method to accumulate boot messages and send them in big chunks to AIO
            if self.device.booting:
                if not self.device.logdata:
                    self.device.logdata = msg
                else:
                    self.device.logdata += '\n'+msg

            # Don't include the "INFO" in the string, because this used a lot,
            # and is effectively the default.
            text = msg
        else:
            text = f'{logging._level_for(level)} {msg}'

        # Print to Serial
        print(text)

        # Print to AIO, only if level is WARNING or higher
        #   AND we are connected to AIO
        #   AND we are not currently throttled
        if (self.aio 
            and not self.aio.throttled
            and level >= logging.WARNING):
            
            try:
                print('debug - sending log to AIO')
                self.aio.send_data(f'{self.aio.group}.log', text)
            except Exception as e:
                print(f'Error publishing to AIO log: {e}')

        # Print to log.txt with timestamp 
        # only works if flash is set writable at boot time
        # try:
        #     with open('log.txt', 'a+') as f:
        #         ts = self.device.get_timestamp() #timestamp from the RTC
        #         text = f'{ts} {text}\r\n'
        #         f.write(text)
        # except OSError as e:
        #     print(f'FS not writable {self.format(level, msg)}')
        #     if e.args[0] == 28:  # If the file system is full...
        #         print(f'Filesystem full')

        # Print to SDCARD log.txt with timestamp 
        # only works if attach_sd_card() function has been run.
        if self.device.sdcard:
            try:
                with open('/sd/log.txt', 'a') as f:
                    ts = self.device.get_timestamp() #timestamp from the RTC
                    text = f'{ts} {text}\r\n'
                    f.write(text)
            except OSError as e:
                print(f'SDCard FS not writable {e}')

