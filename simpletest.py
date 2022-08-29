from circuitpy_mcu.ota_bootloader import reset, enable_watchdog
from circuitpy_mcu.mcu import Mcu
import time
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
        '0x72' : 'Sparkfun LCD Display',
        '0x77' : 'Temp/Humidity/Pressure BME280' # Built into some ESP32S2 feathers 
    }

    mcu = Mcu(loglevel=LOGLEVEL)

    # External I2C display
    mcu.attach_display_sparkfun_20x4()

    # Use the Adalogger RTC chip rather than ESP32-S2 RTC
    mcu.attach_rtc_pcf8523()

    # Use SD card
    if mcu.attach_sdcard():
        mcu.delete_archive()
        mcu.archive_file('log.txt')

    # Networking Setup
    mcu.wifi.connect()
    mcu.aio_setup(aio_group = f'{AIO_GROUP}-{mcu.id}')
    mcu.aio.subscribe('led-color')

    def usb_serial_parser(string):
        mcu.log.info(f'USBserial: {string}')

    def parse_feeds():
        if mcu.aio is not None:
            for feed_id in mcu.aio.updated_feeds.keys():
                payload = mcu.aio.updated_feeds.pop(feed_id)

                if feed_id == 'led-color':
                    r = int(payload[1:3], 16)
                    g = int(payload[3:5], 16)
                    b = int(payload[5:], 16)
                    mcu.display.set_fast_backlight_rgb(r, g, b)
                    mcu.pixel[0] = int(payload[1:], 16)
                    # mcu.pixel[0] = (r<<16) + (g<<8) + b

                if feed_id == 'ota':
                    mcu.ota_reboot()

    timer_A=0

    while True:
        mcu.service(serial_parser=usb_serial_parser)


        if time.monotonic() - timer_A > 1:
            timer_A = time.monotonic()
            timestamp = mcu.get_timestamp()
            mcu.data['debug'] = timestamp
            mcu.display_text(timestamp)
            mcu.aio_sync(receive_interval=10, publish_interval=10)
            parse_feeds()


if __name__ == "__main__":
    try:
        enable_watchdog(timeout=60)
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)