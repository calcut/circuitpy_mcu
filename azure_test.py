import time
import board
from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.display import LCD_20x4
import busio

# scheduling and event/error handling libs
from watchdog import WatchDogTimeout
import supervisor
import microcontroller
import adafruit_logging as logging
import traceback

from adafruit_azureiot import IoTCentralDevice,  IoTHubDevice
import adafruit_requests
from secrets import secrets
import json
import random
import rtc
import socketpool
import wifi
import ssl

SIMPLETEST = False
# AIO = False
AZURE = True
# AZURE = False

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/calcut/circuitpy-septic_tank"
__filename__ = "azure_test.py"

def main():

    # Optional list of expected I2C devices and addresses
    # Maybe useful for automatic configuration in future
    i2c_dict = {
        '0x0B' : 'Battery Monitor LC709203', # Built into ESP32S2 feather 
        '0x72' : 'Sparkfun LCD Display',
        # '0x40' : 'Temp/Humidity HTU31D',

    }

    uart = busio.UART(board.TX, board.RX, baudrate=57600)

    # instantiate the MCU helper class to set up the system
    mcu = Mcu()

    # Check what devices are present on the i2c bus
    mcu.i2c_identify(i2c_dict)

    try:
        display = LCD_20x4(mcu.i2c)
        mcu.attach_display(display)
        display.show_text(__filename__)

    except Exception as e:
        mcu.log_exception(e)
        mcu.pixel[0] = mcu.pixel.RED

    # if SIMPLETEST:
    #     print("Connecting to WiFi...")
    #     wifi.radio.connect(secrets["ssid"], secrets["password"])
    #     # mcu.wifi_connect()
    #     pool = socketpool.SocketPool(wifi.radio)
    #     requests = adafruit_requests.Session(pool, ssl.create_default_context())

    #     response = requests.get("https://io.adafruit.com/api/v2/time/seconds")
    #     if response:
    #         if response.status_code == 200:
    #             r = rtc.RTC()
    #             # mcu.rtc.datetime = time.localtime(int(response.text))
    #             r.datetime = time.localtime(int(response.text))
    #             print(f"System Time: {r.datetime}")
    #             response.close()
    #         else:
    #             print("Setting time failed")

    #     requests._free_sockets()

    #     # Create an instance of the Azure IoT Central device
    #     device = IoTCentralDevice(pool, None, secrets["id_scope"], secrets["device_id"], secrets["device_sas_key"])
    #     print("Connecting to Azure IoT Central...")
    #     device.connect()
    #     print("Connected to Azure IoT Central...")

    if AZURE:
        mcu.wifi_connect()
        mcu.azure_setup()

        message_counter = 60

        while True:
            try:
                mcu.watchdog.feed()
                # Send telemetry every minute
                # You can see the values in the devices dashboard
                if message_counter >= 60:
                    message = {"Temperature": random.randint(0, 50)}
                    # mcu.azure_device.send_telemetry(json.dumps(message))
                    mcu.azure_device.send_device_to_cloud_message(json.dumps(message))
                    message_counter = 0
                else:
                    message_counter += 1

                # Poll every second for messages from the cloud
                mcu.azure_device.loop()
            except (ValueError, RuntimeError) as e:
                print("Connection error, reconnecting\n", str(e))
                wifi.radio.enabled = False
                wifi.radio.enabled = True
                wifi.radio.connect(secrets["ssid"], secrets["password"])
                mcu.azure_device.reconnect()
                continue
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')
        # May want to add code to stop gracefully here 
        # e.g. turn off relays or pumps
        
    except WatchDogTimeout:
        print('Code Stopped by WatchDog Timeout!')
        # supervisor.reload()
        # NB, sometimes soft reset is not enough! need to do hard reset here
        # print('Performing hard reset in 15s')
        # time.sleep(15)
        # microcontroller.reset()

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        print(traceback.format_exception(None, e, e.__traceback__))
        # Can we log here?
        # print('Performing a hard reset in 15s')
        # time.sleep(15) #Make sure this is shorter than watchdog timeout
        # # supervisor.reload()
        # microcontroller.reset()