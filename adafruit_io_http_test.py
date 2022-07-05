import time
from random import randint
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.aio import Aio_http
from adafruit_io.adafruit_io import AdafruitIO_RequestError
import adafruit_logging as logging

AIO_GROUP = 'septic-dev-x'
LOGLEVEL = logging.DEBUG


mcu = Mcu(watchdog_timeout=120)




mcu.wifi_connect()
mcu.log.setLevel(LOGLEVEL)

aio = Aio_http(mcu.requests, group=AIO_GROUP, loghandler=mcu.loghandler)


# aio.log.addHandler(mcu.loghandler)
# aio.log.setLevel(LOGLEVEL)

# mcu.subscribe_http('ota')
# mcu.subscribe_http('tc1')
aio.subscribe('test-a')

feeds = {
    'test-a'    : 1,
    'test-b'    : 2,
    'test-c'    : 3,
}

timer_a = 0
while True:
    mcu.watchdog.feed()
    aio.receive(interval=10)
    aio.publish_feeds(feeds, interval=10)
    time.sleep(1)
    print(mcu.get_timestamp())