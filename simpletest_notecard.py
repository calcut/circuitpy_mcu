from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.notecard_manager import Notecard_manager

import busio
import board

import notecard
from notecard import hub, card, file, note, env

import time
import json

import adafruit_logging as logging
from secrets import secrets


__version__ = "v3.0.0_notecard"
__filename__ = "simpletest.py"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

AIO_GROUP = 'dev'
# LOGLEVEL = logging.DEBUG
LOGLEVEL = logging.INFO

def main():

    i2c_dict = {
        '0x0B' : 'Battery Monitor LC709203', # Built into ESP32S2 feather 
        '0x17' : 'BluesWireless Notecard', 
        # '0x68' : 'Realtime Clock PCF8523', # On Adalogger Featherwing
        '0x72' : 'Sparkfun LCD Display',
        # '0x77' : 'Temp/Humidity/Pressure BME280' # Built into some ESP32S2 feathers 
    }

    mcu = Mcu(loglevel=LOGLEVEL)
    mcu.log.info(f'STARTING {__filename__} {__version__}')

    # External I2C display
    mcu.attach_display_sparkfun_20x4()

    ncm = Notecard_manager(loghandler=mcu.loghandler, i2c=mcu.i2c)

    # environment variables, with a default value (to be overridden by notehub)
    env_vars = {
        'pump1-speed' : "0.54",
        'pump2-speed' : "0.55",
        'pump3-speed' : "0.56",
    }

    ncm.env_vars = env_vars

    # set some defaults
    ncm.set_default_envs(env_vars)

    timer_A=0
    timer_B=0
    timer_C=0

    while True:
        mcu.service()
        if time.monotonic() - timer_A > 5:
            timer_A = time.monotonic()
            mcu.led.value = not mcu.led.value #heartbeat LED
            timestamp = mcu.get_timestamp()
            mcu.display_text(timestamp)

            temp = 0.123
            humidity = 0.456
            mcu.data['temp'] = temp
            mcu.data['humidity'] = humidity
            mcu.data['ts'] = timestamp


        if time.monotonic() - timer_B > 20:
            timer_B = time.monotonic()
            timestamp = mcu.get_timestamp()
            ncm.send_note(mcu.data)
            # note.add(ncard, "sensors.qo", { "temp": temp, "time": timestamp}, sync=False)

        if time.monotonic() - timer_C > 30:
            timer_C = time.monotonic()
            timestamp = mcu.get_timestamp()
            mcu.log.info(f"servicing notecard now {timestamp}")
            ncm.service()







    # def usb_serial_parser(string):
    #     mcu.log.info(f'USBserial: {string}')

    # # def parse_feeds():
    # #     if mcu.aio is not None:
    # #         for feed_id in mcu.aio.updated_feeds.keys():
    # #             payload = mcu.aio.updated_feeds.pop(feed_id)

    # #             if feed_id == 'led-color':
    # #                 r = int(payload[1:3], 16)
    # #                 g = int(payload[3:5], 16)
    # #                 b = int(payload[5:], 16)
    # #                 if mcu.display:
    # #                     mcu.display.set_fast_backlight_rgb(r, g, b)
    # #                 mcu.pixel[0] = int(payload[1:], 16)
    # #                 # mcu.pixel[0] = (r<<16) + (g<<8) + b

    # #             if feed_id == 'ota':
    # #                 mcu.ota_reboot()

    # timer_A=0

    # while True:
    #     mcu.service(serial_parser=usb_serial_parser)

    #     if time.monotonic() - timer_A > 1:
    #         timer_A = time.monotonic()
    #         mcu.led.value = not mcu.led.value #heartbeat LED
    #         timestamp = mcu.get_timestamp()
    #         # mcu.data['debug'] = timestamp
    #         mcu.display_text(timestamp)
    #         # mcu.aio_sync_http(receive_interval=10, publish_interval=10)
    #         # parse_feeds()


if __name__ == "__main__":
    try:
        enable_watchdog(timeout=120)
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)