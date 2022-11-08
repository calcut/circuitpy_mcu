from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.notecard_manager import Notecard_manager
import random

import busio
import board

import notecard
from notecard import hub, card, file, note, env

import time
import json

import adafruit_logging as logging
from secrets import secrets


# for streaming to the Initial State Dashboard, I used this JSONata filter on notehub
# This gets the json in the correct format for:
# https://initialstateeventsapi.docs.apiary.io/#reference/event-data/events-json/send-events
# (
#     $f1 := function($k, $v, $e) {$merge([{"key" : $k},{"value" : $v},{"epoch" : $e}])};
#     ($each(body, function($v, $k) {$f1($k, $v, when)}))
# )

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

    ncm = Notecard_manager(loghandler=mcu.loghandler, i2c=mcu.i2c, watchdog=60)

    # environment variables, with a default value (to be overridden by notehub)
    environment_default = {
        'pump1-speed' : "0.54",
        'pump2-speed' : "0.55",
        'pump3-speed' : "0.56",
    }

    # set some defaults
    ncm.set_default_envs(environment_default)

    timer_A=0
    timer_B=0
    timer_C=0

    def parse_environment():

        for key in ncm.environment.keys():
            val = ncm.environment.pop(key)
            mcu.log.info(f"environment update: {key} = {val}")

            if key == 'pump1-speed':
                speed = float(val)
                print(f'Adjusting pump 1 speed to {speed}')

            if key == 'pump2-speed':
                speed = float(val)
                print(f'Adjusting pump 2 speed to {speed}')

    def parse_inbound_note(notefile="data.qi"):

        note = ncm.inbound_notes[notefile]
        if type(note) == dict:
            for key in note.keys():
                val = note.pop(key)
                mcu.log.info(f"parsing {notefile}: {key} = {val}")

                if key == 'test':
                    mcu.log.info(f"Test success! val = {val}")



    while True:
        mcu.service()
        if time.monotonic() - timer_A > 1:
            timer_A = time.monotonic()
            mcu.led.value = not mcu.led.value #heartbeat LED

            timestamp = mcu.get_timestamp()
            mcu.display_text(timestamp)

            mcu.data['temp'] = round(random.uniform(15, 30), 4)
            mcu.data['humidity'] = round(random.uniform(45, 70), 4)



        if time.monotonic() - timer_B > 10:
            timer_B = time.monotonic()
            # timestamp = mcu.get_timestamp()
            mcu.log.info(f"servicing notecard now {timestamp}")

            ncm.add_to_timestamped_note(mcu.data)

            ncm.receive_note()
            parse_inbound_note()

            ncm.receive_environment()
            parse_environment()

        if time.monotonic() - timer_C > 30:
            timer_C = time.monotonic()
            timestamp = mcu.get_timestamp()
            # ncm.send_note(mcu.data, sync=True)
            ncm.send_timestamped_note(sync=True)


if __name__ == "__main__":
    try:
        enable_watchdog(timeout=120)
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)