import time
from random import randint
from circuitpy_mcu.mcu import Mcu
from adafruit_io.adafruit_io import AdafruitIO_RequestError
import adafruit_logging as logging

AIO_GROUP = 'septic-dev'
LOGLEVEL = logging.DEBUG


mcu = Mcu(watchdog_timeout=120)


mcu.wifi_connect()
mcu.aio_setup_http(group=AIO_GROUP)
mcu.log.setLevel(LOGLEVEL)

mcu.subscribe_http('ota')
mcu.subscribe_http('tc1')

timer_a = 0
while True:
    mcu.aio_loop_http()

    if time.monotonic() - timer_a > 5:
        timer_a = time.monotonic()
        mcu.aio_send_http({'temperature' : 4,
                            'tc2'        : 2,   
                            })

