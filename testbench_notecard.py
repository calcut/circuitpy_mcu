from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.notecard_manager import Notecard_manager
import random

import time
import adafruit_logging as logging

import notecard
from notecard import hub, card, file, note, env
from secrets import secrets
import microcontroller




__version__ = "v3.1.0"
__filename__ = "testbench_notecard.py"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

"""
This will try to break things about the notecard and see if exceptions are handled sensibly

- Too many devices on i2c bus
    - tricky one to test, best to keep 2k or more pullups
- Incorrect productID
- Incorrect wifi credentials
- Dropped wifi connection
- wifi connected but no internet
- Exercise Notecard watchdog 
    - make sure ATTN pin is configured to switch feather power
    - make sure feather isn't powered independently via usb
- Exercise ESP32 watchdog 

- Device banned from notehub

- continuous vs periodic modes
- no internet during boot




"""
WATCHDOG_TEST = False
PID_TEST = False

MINUTES = 1 # reduced for debug
# MINUTES = 60 #60seconds
LOGLEVEL = logging.DEBUG
# LOGLEVEL = logging.INFO

def main():

    i2c_dict = {
        '0x0B' : 'Battery Monitor LC709203', # Built into ESP32S2 feather 
        '0x17' : 'BluesWireless Notecard', 
        # '0x68' : 'Realtime Clock PCF8523', # On Adalogger Featherwing
        '0x72' : 'Sparkfun LCD Display',
        # '0x77' : 'Temp/Humidity/Pressure BME280' # Built into some ESP32S2 feathers 
    }

    mcu = Mcu(loglevel=LOGLEVEL, i2c_freq=100000)
    mcu.attach_display_sparkfun_20x4()

    ncm = Notecard_manager(loghandler=mcu.loghandler, i2c=mcu.i2c, watchdog=60, loglevel=LOGLEVEL)

    mcu.log.info(f'STARTING {__filename__} {__version__}')


    # set defaults for environment variables, (to be overridden by notehub)
    env = {
        'pump1-speed' : "0.54",
        'pump2-speed' : "0.55",
        }

    # This will also update env with any overrides from notehub
    ncm.set_default_envs(env)

    def wait_for_watchdog():
        i=0
        while True:
            print(f'waiting for watchdog timeout {i}')
            mcu.display_text(f'watchdog wait {i}')
            time.sleep(1)
            i+=1

    def incorrect_product_id():
        hub.set(ncm.ncard, product="wrong_pid", mode=ncm.mode, sync=True, outbound=2, inbound=2)
        while True:
            ncm.check_status()
            rsp = hub.syncStatus(ncm.ncard)
            print(f'{rsp=}')
            time.sleep(1)
        # hub.set(ncm.ncard, product=secrets['productUID'], mode=ncm.mode, sync=True, outbound=2, inbound=2)        
        microcontroller.reset()



    def parse_environment():
        for key, val in env.items():

            if key == 'pump1-speed':
                speed = float(val)
                print(f'Adjusting pump 1 speed to {speed}')

            if key == 'pump2-speed':
                speed = float(val)
                print(f'Adjusting pump 2 speed to {speed}')

    parse_environment()

    def parse_inbound_note(notefile="data.qi"):

        note = ncm.inbound_notes[notefile]
        if type(note) == dict:
            for key in note.keys():
                val = note.pop(key)
                mcu.log.info(f"parsing {notefile}: {key} = {val}")

                if key == 'test':
                    mcu.log.info(f"Test success! val = {val}")

    timer_A=0
    timer_B=0
    timer_C=0

    while True:
        mcu.service()

        if WATCHDOG_TEST:
            wait_for_watchdog()

        if PID_TEST:
            incorrect_product_id()

        if time.monotonic() - timer_A > 1:
            timer_A = time.monotonic()
            mcu.led.value = not mcu.led.value #heartbeat LED

            timestamp = mcu.get_timestamp()
            mcu.display_text(timestamp)

            # capture data, can be displayed immediately
            mcu.data['temp'] = round(random.uniform(15, 30), 4)
            mcu.data['humidity'] = round(random.uniform(45, 70), 4)


        if time.monotonic() - timer_B > (1 * MINUTES):
            timer_B = time.monotonic()
            mcu.log.debug(f"servicing notecard now {timestamp}")

            ncm.check_status()

            # Accumulate data with timestamps in a note to send infrequently
            # Intended to minimise Notehub consumption credits
            ncm.add_to_timestamped_note(mcu.data)

            # check for any new inbound notes to parse
            ncm.receive_note()
            parse_inbound_note()

            # check for any environment variable updates to parse
            if ncm.receive_environment(env):
                parse_environment()

        if time.monotonic() - timer_C > (15 * MINUTES):
            timer_C = time.monotonic()

            # Send note infrequently (e.g. 15 mins) to minimise consumption credit usage
            ncm.send_timestamped_note(sync=True)
            ncm.send_timestamped_log(sync=True)

            # hub.sync(ncm.ncard)

            # Can also send data without timesamps, current timestamp will be used
            # ncm.send_note(mcu.data, sync=True)


if __name__ == "__main__":
    try:
        enable_watchdog(timeout=240)
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)