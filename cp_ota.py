from lib.circuitpy_mcu.mcu import Mcu
import adafruit_requests
import ssl
import socketpool
import wifi
import dualbank


mcu = Mcu()
mcu.wifi_connect()

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())


url = f'https://downloads.circuitpython.org/bin/adafruit_feather_esp32s2/en_GB/adafruit-circuitpython-adafruit_feather_esp32s2-en_GB-7.2.5.bin'
response = requests.get(url)

chunk_size = 1024
offset=0
for chunk in response.iter_content(chunk_size):
    print(f'offset = {offset}')
    dualbank.flash(chunk, offset=offset)
    offset += chunk_size