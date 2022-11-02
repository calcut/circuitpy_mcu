from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu_notecard import Mcu

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

    # # Networking Setup
    # mcu.wifi.connect()
    # if mcu.aio_setup(aio_group=f'{AIO_GROUP}-{mcu.id}'):
    #     mcu.aio.connect()
    #     mcu.aio.subscribe('led-color')

    # Notecard Setup
    # i2c = busio.I2C(board.SCL, board.SDA)
    ncard = notecard.OpenI2C(mcu.i2c, 0, 0, debug=True)
    productUID = "com.gmail.calum.cuthill:test1"


    def notecard_reconfigure():
        hub.set(ncard, productUID, mode='continuous', sync=True)

        req = {"req": "card.wifi"}
        req["ssid"] = secrets['ssid']
        req["password"] = secrets['password']
        rsp = ncard.Transaction(req)

        req = {"req": "card.restart"}
        ncard.Transaction(req)

    stamp = time.monotonic()
    while True:
        try:
            status = card.status(ncard)
            if "connected" in status:
                print(f'{status["connected"]=}')
                break

            else:
                # check details of connection status
                hub.syncStatus(ncard)

            if time.monotonic() - stamp > 60:
                stamp = time.monotonic()
                print('no connection, reconfiguring notecard')
                notecard_reconfigure()

            
        except OSError as e:
            # notecard may be rebooting
            print(e)

        time.sleep(1)
        
    print("Notecard connected!")

    # sync time
    rsp = card.time(ncard)
    unixtime = rsp['time']
    print(f'{unixtime=}')
    mcu.rtc.datetime = time.localtime(unixtime)

    env_vars = {
        'pump1-speed' : "0.54",
        'pump2-speed' : "0.55",
        'pump3-speed' : "0.56",
    }

    inbound_notes = {
        # 'sensors.qo' : None,
        'data.qi'    : None,
    }

    def set_default_envs(var_dict):
        for key, val in var_dict.items():
            env.default(ncard, key, val)
        hub.sync(ncard)

    def update_envs():
        print("\n\n Receiving Environment Variables")
        
        for k in env_vars.keys():
            rsp = env.get(ncard, k)
            env_vars[k] = rsp["text"]
        print(env_vars)
        print("\n\n")


    def update_notes():
        print("\n\n Receiving Notes")
        for n in inbound_notes.keys():
            rsp = note.get(ncard, n, delete=True)
            if "body" in rsp:
                inbound_notes[n] = rsp["body"]
        print(inbound_notes)
        print("\n\n")

    # set some defaults
    set_default_envs(env_vars)

    timer_A=0
    timer_B=0
    env_stamp = 0

    while True:
        mcu.service()
        if time.monotonic() - timer_A > 5:
            timer_A = time.monotonic()
            mcu.led.value = not mcu.led.value #heartbeat LED
            timestamp = mcu.get_timestamp()
            mcu.display_text(timestamp)

            temp = 0.123
            humidity = 0.456
            note.add(ncard, "sensors.qo", { "temp": temp, "time": timestamp}, sync=True)
            # mcu.aio_sync(mcu.data, publish_interval=10)
            # mcu.aio_sync_http(receive_interval=10, publish_interval=10)
            # parse_feeds()
            # hub.sync(ncard)
            notes_updated = file.changes(ncard)
            if "total" in notes_updated:
                update_notes()

            env_updated = env.modified(ncard)
            if env_updated["time"] > env_stamp:
                update_envs()
                env_stamp = env_updated["time"]

        if time.monotonic() - timer_B > 5:
            timer_B = time.monotonic()
            timestamp = mcu.get_timestamp()
            note.add(ncard, "sensors.qo", { "temp": temp, "time": timestamp}, sync=True)









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