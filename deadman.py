import board
import time
from digitalio import DigitalInOut, Pull

DEBUG = False
# DEBUG = True


detect_pin = DigitalInOut(board.D11)
detect_pin.switch_to_input(Pull.UP)

output_enable_pin = DigitalInOut(board.D12)
output_enable_pin.switch_to_output(True)


led = DigitalInOut(board.LED)
led.switch_to_output()

# # Run something like this on the main board
if DEBUG:
    feed_pin =  DigitalInOut(board.D10)
    feed_pin.switch_to_output()
    timer_feed = 0


timer = 0
while True:

    # simulate a main board toggling a pin should not be faster than every second.
    if DEBUG:
        print(f'last toggle was {time.monotonic() - timer}s ago')
        if time.monotonic() - timer_feed > 2:
            timer_feed = time.monotonic()
            feed_pin.value = not feed_pin.value

    previous_value = led.value
    led.value = detect_pin.value
    if led.value != previous_value:
        # reset the timer if a toggle is detected
        timer = time.monotonic()

    if time.monotonic() - timer > 240:
        timer = time.monotonic()
        print('no toggle for 4 mins, pulling down output_enable pin for 3s')
        output_enable_pin.value = False
        for x in range(30):
            led.value = not led.value
            time.sleep(0.1)
        output_enable_pin.value = True

    time.sleep(0.4)