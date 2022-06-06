import adafruit_requests
import ssl
import socketpool
import wifi
import dualbank
from secrets import secrets
import microcontroller

print('connecting to wifi')
wifi.radio.connect(secrets["ssid"], secrets["password"])
print('wifi connected')

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# see https://github.com/adafruit/circuitpython/issues/6448

url = 'https://adafruit-circuit-python.s3.amazonaws.com/bin/adafruit_feather_esp32s2/en_GB/adafruit-circuitpython-adafruit_feather_esp32s2-en_GB-7.3.0.bin'
# url= 'https://adafruit-circuit-python.s3.amazonaws.com/bin/adafruit_feather_esp32s2/en_GB/adafruit-circuitpython-adafruit_feather_esp32s2-en_GB-7.2.5.bin'

offset=65536
position = 0
header = {}
header["Range"] = f"bytes={offset}-"
response = requests.get(url, headers=header)
length = int(response.headers["content-length"])

for chunk in response.iter_content(chunk_size=8192):
    actual_chunk_size = len(chunk)
    print(f'{position=} {round(position/length*100, 1)}%')
    try:
        dualbank.flash(chunk, offset=position)
        position += actual_chunk_size
    except RuntimeError as e:
        print(f'RuntimeError: {e}')
        print('switching OTA banks and resetting')
        dualbank.switch()
        microcontroller.reset()
        

print('flash complete')
dualbank.switch()
microcontroller.reset()