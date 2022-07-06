import time
from random import randint
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.aio import Aio_http
from adafruit_io.adafruit_io import AdafruitIO_RequestError
import adafruit_logging as logging

# scheduling and event/error handling libs
from watchdog import WatchDogTimeout
import supervisor
import microcontroller
import adafruit_logging as logging
import traceback

AIO_GROUP = 'septic-dev-x'
LOGLEVEL = logging.DEBUG


def main():
    mcu = Mcu()

    mcu.wifi_connect()
    mcu.log.setLevel(LOGLEVEL)
    mcu.attach_sdcard()
    mcu.delete_archive()
    mcu.archive_file('log.txt')


    aio = Aio_http(mcu.requests, group=AIO_GROUP, loghandler=mcu.loghandler)
    mcu.loghandler.aio = aio

    aio.log.addHandler(mcu.loghandler)
    aio.log.setLevel(LOGLEVEL)

    # aio.subscribe('test-a')

    feeds = {
        'test-a'    : 1,
        'test-b'    : 2,
        'test-c'    : 3,
    }

    timer_a = 0
    while True:
        microcontroller.watchdog.feed()
        # aio.receive(interval=10)
        # aio.publish_feeds(feeds, interval=10)
        time.sleep(15)
        print(mcu.get_timestamp())
        mcu.log.warning('log test test')
        # print(2/0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        detail = traceback.format_exception(None, e, e.__traceback__)
        print(detail)