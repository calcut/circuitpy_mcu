from adafruit_motorkit import MotorKit
from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.display import LCD_20x4


import adafruit_pcf8523
import time
import busio
import board

# scheduling and event/error handling libs
from watchdog import WatchDogTimeout
import microcontroller
import adafruit_logging as logging

__filename__ = "simpletest.py"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

AIO_GROUP = 'dev'
# LOGLEVEL = logging.DEBUG
LOGLEVEL = logging.INFO

def main():

    i2c_dict = {
        '0x0B' : 'Battery Monitor LC709203', # Built into ESP32S2 feather 
        '0x68' : 'Realtime Clock PCF8523', # On Adalogger Featherwing
        '0x78' : 'Motor Featherwing PCA9685', #Solder bridge on address bit A4 and A3
        '0x72' : 'Sparkfun LCD Display',
        '0x77' : 'Temp/Humidity/Pressure BME280' # Built into some ESP32S2 feathers 
    }

    mcu = Mcu(loglevel=LOGLEVEL)

    display = LCD_20x4(mcu.i2c)
    mcu.attach_display(display, showtext = __filename__) # to show wifi/AIO status etc.

    # Networking Setup
    mcu.wifi.connect()
    mcu.aio_setup(aio_group = f'{AIO_GROUP}-{mcu.id}')

    def usb_serial_parser(string):
        mcu.log.info(f'USBserial: {string}')


    timer_A=0

    while True:
        mcu.service(serial_parser=usb_serial_parser)


        if time.monotonic() - timer_A > 1:
            timer_A = time.monotonic()
            timestamp = mcu.get_timestamp()
            mcu.data['debug'] = timestamp
            mcu.display_text(timestamp)
            mcu.aio_sync()


if __name__ == "__main__":
    try:
        enable_watchdog(timeout=60)
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)