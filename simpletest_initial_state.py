from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.initial_state import Initial_state_streamer

import random

import time
import adafruit_logging as logging


__version__ = "v3.0.0_notecard"
__filename__ = "simpletest_initial_state.py"
__repo__ = "https://github.com/calcut/circuitpy-mcu"


MINUTES = 1 # reduced for debug
# MINUTES = 60 #60seconds
LOGLEVEL = logging.DEBUG
# LOGLEVEL = logging.INFO

def main():

    i2c_dict = {
        '0x0B' : 'Battery Monitor LC709203', # Built into ESP32S2 feather 
        # '0x68' : 'Realtime Clock PCF8523', # On Adalogger Featherwing
        '0x72' : 'Sparkfun LCD Display',
        # '0x77' : 'Temp/Humidity/Pressure BME280' # Built into some ESP32S2 feathers 
    }

    mcu = Mcu(loglevel=LOGLEVEL, i2c_freq=100000)
    mcu.log.info(f'STARTING {__filename__} {__version__}')

    # Networking Setup
    mcu.wifi.connect()
    istate = Initial_state_streamer(mcu.wifi.requests)




    timer_A=0
    timer_B=0
    timer_C=0

    while True:
        mcu.service()
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

            # Accumulate data with timestamps in a note to send infrequently
            # Intended to minimise Notehub consumption credits
            # ncm.add_to_timestamped_note(mcu.data)

            # check for any new inbound notes to parse
            # ncm.receive_note()
            # parse_inbound_note()

            # check for any environment variable updates to parse
            # ncm.receive_environment()
            # parse_environment()

        if time.monotonic() - timer_C > (15 * MINUTES):
            timer_C = time.monotonic()

            # Send note infrequently (e.g. 15 mins) to minimise consumption credit usage
            # ncm.send_timestamped_note(sync=True)
            # ncm.send_timestamped_log(sync=True)

            # Can also send data without timesamps, current timestamp will be used
            istate.send_data(mcu.data)



if __name__ == "__main__":
    try:
        enable_watchdog(timeout=240)
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)