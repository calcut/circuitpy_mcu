from circuitpy_mcu.mcu import Mcu
from circuitpy_mcu.display import LCD_20x4
# import adafruit_requests
# import ssl
# import socketpool
# import wifi
# import dualbank
import time
import os

AIO_GROUP = 'septic-dev'
OTA_LIST_URL = 'https://raw.githubusercontent.com/calcut/circuitpy_septic_tank/main/ota_list.py'


i2c_dict = {
    '0x0B' : 'Battery Monitor LC709203', # Built into ESP32S2 feather 
    '0x48' : 'ADC for pH Probes ADC1115',
    '0x60' : 'Thermocouple Amp MCP9600',
    '0x61' : 'Thermocouple Amp MCP9600',
    '0x62' : 'Thermocouple Amp MCP9600',
    '0x63' : 'Thermocouple Amp MCP9600',
    '0x64' : 'Thermocouple Amp MCP9600',
    '0x65' : 'Thermocouple Amp MCP9600',
    '0x66' : 'Thermocouple Amp MCP9600',
    '0x67' : 'Thermocouple Amp MCP9600',
    '0x68' : 'Realtime Clock PCF8523', # On Adalogger Featherwing
    '0x70' : 'Motor Featherwing PCA9685', #Solder bridge on address bit A4
    '0x72' : 'Sparkfun LCD Display',
    '0x77' : 'Temp/Humidity/Pressure BME280' # Built into some ESP32S2 feathers 
}

mcu = Mcu(watchdog_timeout=130)
mcu.i2c_identify()
display = LCD_20x4(mcu.i2c)
mcu.attach_display(display) # to show wifi/AIO status etc.
mcu.attach_sdcard()
mcu.wifi_connect()
mcu.aio_setup(log_feed=None, group=AIO_GROUP)

def get_ota_list(url):

    aio_reconnect_after = False
    if mcu.aio_connected:
            # Have not figured out how to make this work when AIO is connected.
            # All sorts of SSL related errors happen
        mcu.io.disconnect()
        aio_reconnect_after = True

    try:
        print(f'trying to fetch ota files defined in {url}')
        response = mcu.requests.get(url)
        ota_list = response.json()

        for path, list_url in ota_list.items():

            dirs = path.split('/')[1:-1]
            for i in range(len(dirs)):
                d = ''
                for n in range(i+1):
                    d+=f'/{dirs[n]}'
                try:
                    os.mkdir(d)  
                    print(f'created dir {d}')
                except Exception as e:
                    if e.args[0] == 30:
                        print('Read Only Filesystem. Is the SD card mounted?')
                    if e.args[0] == 17:
                        # Directory already exists
                        pass
                    else:
                        print(f'Trying to mkdir {d}')
                        print(e)

            print(f'saving {list_url} to {path}')
            file = mcu.requests.get(list_url).content
            with open(path, 'w') as f:
                f.write(file)
            print(f'reading {path}')
            with open(path, 'r') as f:
                line = f.readline()
                while line != '':
                    print(line)
                    line = f.readline()

        mcu.requests._free_sockets()
        if aio_reconnect_after:
            mcu.io.connect()

    except Exception as e:
        print(e)
        print(f'Could not get {url}')
        return False

while True:
    mcu.watchdog.feed()
    print('receiving')
    mcu.aio_receive()
    mcu.io.get(f'{AIO_GROUP}.ota')

    if mcu.ota_requested:
        get_ota_list(OTA_LIST_URL)
        mcu.ota_requested = False

    print('importing')


    print('sleeping 3')
    time.sleep(3)

# pool = socketpool.SocketPool(wifi.radio)
# requests = adafruit_requests.Session(pool, ssl.create_default_context())


# url = f'https://downloads.circuitpython.org/bin/adafruit_feather_esp32s2/en_GB/adafruit-circuitpython-adafruit_feather_esp32s2-en_GB-7.2.5.bin'
# response = requests.get(url)

# chunk_size = 1024
# offset=0
# for chunk in response.iter_content(chunk_size):
#     print(f'offset = {offset}')
#     dualbank.flash(chunk, offset=offset)
#     offset += chunk_size