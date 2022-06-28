import time
from random import randint
from circuitpy_mcu.mcu import Mcu
from adafruit_io.adafruit_io import AdafruitIO_RequestError

AIO_GROUP = 'septic-dev'


mcu = Mcu(watchdog_timeout=120)


mcu.wifi_connect()
mcu.aio_setup_http(group=AIO_GROUP)


try:
    # Get the 'temperature' feed from Adafruit IO
    temperature_feed = mcu.io.get_feed("temperature")
    print(f'{type(temperature_feed)=}')
    print(f'{temperature_feed=}')
except AdafruitIO_RequestError:
    # If no 'temperature' feed exists, create one
    temperature_feed = mcu.io.create_new_feed("temperature")

# gp = mcu.io.get_group('septic-dev')
# print(f'{gp=}')

while True:
    mcu.aio_loop_http()
    time.sleep(1)

# Send random integer values to the feed
random_value = randint(0, 50)
print(f"Sending {random_value} to temperature feed...")
print(f"{temperature_feed['key']=}")
mcu.io.send_data(temperature_feed["key"], random_value)
print("Data sent!")

# Retrieve data value from the feed
print("Retrieving data from temperature feed...")
received_data = mcu.io.receive_data(temperature_feed["key"])
print(f'{type(received_data)=}')
print("Data from temperature feed: ", received_data["value"])

received_data = mcu.io._get('https://io.adafruit.com/api/v2/time/seconds')
print(f'{received_data=}')
print("Data from time feed: ", received_data["value"])

