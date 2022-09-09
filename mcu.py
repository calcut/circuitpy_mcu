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
from circuitpy_mcu.aio import Aio_http, Aio_mqtt
from circuitpy_mcu.wifi_manager import Wifi_manager

try:
    # RTC on adalogger board
    import adafruit_pcf8523
except:
    pass

try:
    # Import Known display types
    from circuitpy_mcu.display import LCD_16x2, LCD_20x4
except:
    pass


__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

class Mcu():
    def __init__(self, i2c_freq=50000, i2c_lookup=None, uart_baud=None, wifi=True, loglevel=logging.INFO):

        uid = microcontroller.cpu.uid
        self.id = f'{uid[-2]:02x}{uid[-1]:02x}'

        # Initialise some key variables

        self.aio_log_feed = None
        self.aio = None
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
        self.log.level = loglevel

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

        self.aio_group = None

        if wifi:
            self.wifi = Wifi_manager(loghandler=self.loghandler)
            self.wifi.log.setLevel(self.log.level)
        else:
            self.wifi = None

    def service(self, serial_parser=None):
        self.watchdog_feed()
        self.read_serial(send_to=serial_parser)
        # if self.wifi:
        #     if self.wifi.connected:
        #         self.pixel[0] = self.pixel.CYAN
        #     else:
        #         self.pixel[0] = self.pixel.RED

    def watchdog_feed(self):
        try:
            microcontroller.watchdog.feed()
        except ValueError:
            # Happens if watchdog timer hasn't been started
            pass

    def aio_setup(self, aio_group=None, http=False):
        try:
            if aio_group:
                self.aio_group = aio_group
            if self.aio_group == None:
                self.aio_group = self.id

            self.log.info(f"Setting up AIO connection with group={self.aio_group}")

            if http:
                self.aio = Aio_http(self.wifi.requests, self.aio_group, self.loghandler)
            else:
                self.aio = Aio_mqtt(self.wifi.pool, self.aio_group, self.loghandler)
            self.aio.log.setLevel(self.log.level)
            self.loghandler.aio = self.aio
            self.aio.rtc = self.rtc
            if not self.wifi.connectivity_check(host='adafruit.com'):
                raise ConnectionError('aio_setup: WiFi reconnection requested')
            self.aio.connect()
            return True

        except Exception as e:
            self.handle_exception(e)

    def aio_sync_http(self, receive_interval=10, publish_interval=10):
        try:
            if not self.wifi.connectivity_check(host='adafruit.com'):
                self.log.info('aio_sync cancelled: no wifi connection')
                return False
            if self.aio:
                self.aio.receive(interval=receive_interval)
                self.aio.publish_feeds(self.data, interval=publish_interval, location=None)
            else:
                self.log.warning('aio_sync failed, aio_setup() will be re-run')
                self.aio_setup()
                self.aio_sync_http()

            return True

        except Exception as e:
            self.handle_exception(e)
            self.aio_sync_http()

    def aio_sync(self, data_dict, publish_interval=10):
        try:
            if self.wifi.offline_mode:
                self.log.debug('aio_sync cancelled: wifi in offline mode')
                self.wifi.connectivity_check()
                return False
            if not self.aio:
                self.log.error('please run aio_setup first')
                return False
            if not self.aio.connected:
                self.log.warning('AIO not connected, trying to connect now')
                self.aio.connect()

            self.aio.sync(data_dict, loop_timeout=0, publish_interval=publish_interval)
            return True

        except Exception as e:
            self.handle_exception(e)

    def i2c_power_on(self):
        # Due to board rev B/C differences, need to read the initial state
        # https://learn.adafruit.com/adafruit-esp32-s2-feather/i2c-power-management
        self.i2c_power.switch_to_input()
        time.sleep(0.01)  # wait for default value to settle
        rest_level = self.i2c_power.value

        self.i2c_power.switch_to_output(value=(not rest_level))
        time.sleep(1.5) # Sometimes even 1s is not enough for e.g. i2c displays. Worse in the heat?

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


    def get_timestamp(self):
        t = self.rtc.datetime
        string = f'{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} {t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}'
        return string

    def attach_display(self, display_object, showtext=None):
        try:
            self.display = display_object
            self.log.info('found display')
            if showtext:
                self.display_text(showtext)
        except Exception as e:
            self.display = None
            self.handle_exception(e)

    def attach_rtc_pcf8523(self):
        try:
            self.rtc = adafruit_pcf8523.PCF8523(self.i2c)
            self.log.info("Using external RTC PCF8523")
        except ValueError as e:
            self.log.warning(f'No RTC found: {e}')

    def attach_display_sparkfun_20x4(self):
        try:
            display = LCD_20x4(self.i2c)
            self.attach_display(display)
        except ValueError as e:
            self.log.warning(f'No Display found: {e}')

    def attach_sdcard(self, cs_pin=board.D10):
        
        try:
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
            cs = digitalio.DigitalInOut(cs_pin)
            self.sdcard = adafruit_sdcard.SDCard(spi, cs)
            vfs = storage.VfsFat(self.sdcard)
            storage.mount(vfs, "/sd")
            self.display_text('SD Card Mounted')
            self.log.info('SD Card Mounted')
            return True
        except OSError:
            self.sdcard = None
            self.log.warning('SD Card not mounted')
            return False
        except Exception as e:
            self.sdcard = None
            self.handle_exception(e)

    def delete_archive(self, archive_dir='/sd/archive'):
        try:
            list = os.listdir(archive_dir)
            for f in list:
                filepath = f'{archive_dir}/{f}'
                os.remove(filepath)
                self.log.info(f'Deleted {filepath}')
        except:
            self.log.warning(f'{archive_dir} directory not found to delete')
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

        try:
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

            try:
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                    self.log.info(f'---Last 10 lines of previous log {filepath}---')
                    for l in lines[-10:]:
                        self.log.info(l[:-1])
                    self.log.info('--End of Previous log---')
            except MemoryError as e:
                self.log.warning('MemoryError reading file before archive: size may be too big')

            os.rename(filepath, newpath)
            self.log.info(f'{filepath} moved to {newpath}')
        except Exception as e:
            self.handle_exception(e)

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
                self.watchdog_feed()
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

    def handle_exception(self, e):

        cl = e.__class__
        if cl == ConnectionError:
            self.log.warning(f'ConnectionError at mcu level, forwarding to wifi handler')
            self.wifi.handle_exception(e)
        else:
            # formats an exception to print to log as an error,
            # includues the traceback (to show code line number)
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.warning(f'No handler for this exception in mcu.handle_exception()')
            # raise


class McuLogHandler(logging.Handler):

    def __init__(self, mcu_device):
        self.aio = None # This can be passed later after aio connection is established
        self.device = mcu_device
        self.boot_time = time.monotonic()

    def emit(self, record):
        """Generate the message and write it to the AIO Feed.

        :param level: The level at which to log
        :param msg: The core message

        """

        if record.levelno == 25:
            # Special handling for messages to be displayed on an attached display
            self.device.display_text(record.msg)
            return


        if record.levelno == logging.INFO:

            # This is a method to accumulate boot messages and send them in big chunks to AIO
            if self.device.booting:
                if not self.device.logdata:
                    self.device.logdata = record.msg
                else:
                    self.device.logdata += '\n'+record.msg

            # Don't include the "INFO" in the string, because this used a lot,
            # and is effectively the default.
            text = f'{record.name} {record.msg}'
        else:
            text = f'{record.name} {record.levelname} {record.msg}'

        # Print to Serial
        print(text)

        # Print to AIO, only if level is WARNING or higher
        #   AND we are connected to AIO
        #   AND we are not currently throttled
        if (self.device.aio
            and self.device.wifi.connected
            and self.device.aio.connected
            and not self.device.aio.throttled
            and record.levelno >= logging.WARNING):
            
            try:
                print('debug - sending log to AIO')
                self.device.aio.send_data(f'{self.device.aio.group}.log', text)
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
            except RuntimeError as e:
                print(f"SDcard RuntimeError: {e}")
                print(f"While attempting to write {text}")

