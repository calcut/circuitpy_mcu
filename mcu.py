# A helper library targeted at using Adafruit ESP32S2 Feather in a datalogger /
# iot controller.
# Essentially this just abstracts some common code to have a simpler top level.

# System and timing
import time
import rtc
import microcontroller
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

try:
    # Import Known display types
    from circuitpy_mcu.display import LCD_16x2, LCD_20x4
except ImportError as e:
    print(str(e))


__version__ = "v3.1.4"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

class Mcu():
    def __init__(self, i2c_freq=50000, i2c_lookup=None, uart_baud=None, loglevel=logging.INFO):

        uid = microcontroller.cpu.uid
        self.id = f'{uid[-2]:02x}{uid[-1]:02x}'

        self.display = None
        self.serial_buffer = ''
        self.data = {} # A dict to store datapoints as they are captured

        # Real Time Clock in ESP32-S2 can be used to track timestamps
        self.rtc = rtc.RTC()

        # Set up logging
        # See McuLogHandler for details
        self.log = logging.getLogger('mcu')
        self.loghandler = McuLogHandler(self)
        self.log.addHandler(self.loghandler)
        self.log.setLevel(loglevel)

        # Pull the I2C power pin low to enable I2C power
        self.log.info('Powering up I2C bus')
        self.i2c_power = digitalio.DigitalInOut(board.I2C_POWER)

        # Due to board rev B/C differences, need to read the initial state
        # https://learn.adafruit.com/adafruit-esp32-s2-feather/i2c-power-management
        self.i2c_power.switch_to_input()
        time.sleep(0.01)  # wait for default value to settle
        self.i2c_off_level = self.i2c_power.value

        self.i2c_power_on()
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=i2c_freq)

        self.i2c2 = None

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

    def service(self, serial_parser=None):
        self.watchdog_feed()
        self.read_serial(send_to=serial_parser)

    def watchdog_feed(self):
        try:
            microcontroller.watchdog.feed()
        except ValueError:
            # Happens if watchdog timer hasn't been started
            pass

    def i2c_power_on(self):
        self.i2c_power.switch_to_output(value=(not self.i2c_off_level))
        time.sleep(1.5) # Sometimes even 1s is not enough for e.g. i2c displays. Worse in the heat?

    def i2c_power_off(self):
        self.i2c_power.switch_to_output(value=self.i2c_off_level)
        time.sleep(1)

    def enable_i2c2(self, sda=board.D6, scl=board.D5, frequency=50000):
        """
        A 2nd i2c bus is helpful to avoid issues with too many devices on a single bus
        e.g. Notecard i2c comms will fail if there are too many pull-up resistors
        """
        self.i2c2 = busio.I2C(sda=sda, scl=scl, frequency=frequency)

    def i2c_identify(self, i2c_lookup=None, i2c=None):
        if i2c is None:
            i2c=self.i2c

        while not i2c.try_lock():  pass

        if i2c_lookup:
            self.log.info(f'\nChecking if expected I2C devices are present:')
            
            lookup_result = i2c_lookup.copy()
            devs_present = []
            for addr in i2c.scan():
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
            for device_address in i2c.scan():
                addr_hex = f'0x{device_address:0{2}X}'
                self.log.info(f'{addr_hex}')
            lookup_result = None

        i2c.unlock()
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

    def attach_display_sparkfun_20x4(self):
        try:
            display = LCD_20x4(self.i2c)
            self.attach_display(display)
        except ValueError as e:
            self.log.warning(f'No Display found: {e}')

    def display_text(self, text):
        if self.display:

            if isinstance(self.display, LCD_16x2):
                self.display.clear()
                self.display.write(text)
            elif isinstance(self.display, LCD_20x4):
                self.display.clear()
                # Unsure why this fails if longer than ~33 chars?
                self.display.write(text[:32])
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
        """
        Checks if there is any input on the usb serial port.
        Typically this would be a keyboard input as part of a user interface.

        If a complete line is detected, it will pass the string to the function: send_to()
        """
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

        """
        A wrapper for read_serial() that waits for a complete input line.
        Input validation is possible by providing a list of expected inputs.
        """
        
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

        # formats an exception to print to log as an error,
        # includues the traceback (to show code line number)
        self.log.error(traceback.format_exception(None, e, e.__traceback__))
        self.log.warning(f'No handler for this exception in mcu.handle_exception()')
        # raise

    def get_next_alarm(self, alarm_list):
        """
        Returns number of seconds until the next alarm in a list,
        e.g. alarm_list = ["10:00", "11:00", "14:53"]
        Assumes alarms repeat daily
        """

        now = time.localtime()
        year = now.tm_year
        month = now.tm_mon
        day = now.tm_mday

        seconds_list = []

        for t in alarm_list:
            sp = t.split(":")

            hour = int(sp[0])
            mins = int(sp[1])

            list_time = time.struct_time([year,month,day,hour,mins, 0,0,0,0])
            posix_list_time = time.mktime(list_time)
            seconds_to_alarm = posix_list_time - time.time()

            # roll over to the next day
            if seconds_to_alarm <=0:
                seconds_to_alarm += 60*60*24

            seconds_list.append(seconds_to_alarm)

        next_alarm_countdown = min(seconds_list)

        return next_alarm_countdown


class McuLogHandler(logging.Handler):

    def __init__(self, mcu_device):
        self.device = mcu_device
        self.aux_log_function = None

    def emit(self, record):

        if record.levelno == 25:
            # Special handling for messages to be displayed on an attached display
            self.device.display_text(record.msg)
            return

        if record.levelno == logging.INFO:
            # Don't include the "INFO" in the string, because this used a lot,
            # and is effectively the default.
            text = f'{record.name} {record.msg}'
        else:
            text = f'{record.name} {record.levelname} {record.msg}'

        # Print to Serial
        print(text)

        if self.aux_log_function is not None:
            # to call an auxilliary log output function (e.g. Send via Notecard)
            try:
                self.aux_log_function(record)
            except Exception as e:
                print(f'Error in aux log function: {e}')

