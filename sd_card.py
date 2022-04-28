from lib.circuitpy_mcu.mcu import Mcu
import adafruit_requests
import ssl
import socketpool
import wifi
import dualbank

import board
import busio
import digitalio
import adafruit_sdcard
import storage
import os


spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D10)
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")


with open("/sd/test.txt", "w") as f:
    f.write("Hello world!\r\n")

with open("/sd/test.txt", "r") as f:
    print("Read line from file:")
    print(f.readline())



# mcu = Mcu()
# mcu.wifi_connect()

# pool = socketpool.SocketPool(wifi.radio)
# requests = adafruit_requests.Session(pool, ssl.create_default_context())


# url = f'https://downloads.circuitpython.org/bin/adafruit_feather_esp32s2/en_GB/adafruit-circuitpython-adafruit_feather_esp32s2-en_GB-7.2.5.bin'
# response = requests.get(url)

# chunk_size = 1024
# offset=0
# with open("/sd/ota.bin", "w") as f:
#     for chunk in response.iter_content(chunk_size):
#         f.write(chunk)
#         print(f"{offset=}")
#         offset += chunk_size
#         mcu.watchdog.feed()

# for chunk in response.iter_content(chunk_size):
#     print(f'offset = {offset}')
#     dualbank.flash(chunk, offset=offset)
#     offset += chunk_size

def print_directory(path, tabs=0):
    for file in os.listdir(path):
        stats = os.stat(path + "/" + file)
        filesize = stats[6]
        isdir = stats[0] & 0x4000

        if filesize < 1000:
            sizestr = str(filesize) + " by"
        elif filesize < 1000000:
            sizestr = "%0.1f KB" % (filesize / 1000)
        else:
            sizestr = "%0.1f MB" % (filesize / 1000000)

        prettyprintname = ""
        for _ in range(tabs):
            prettyprintname += "   "
        prettyprintname += file
        if isdir:
            prettyprintname += "/"
        print('{0:<40} Size: {1:>10}'.format(prettyprintname, sizestr))

        # recursively print directory contents
        if isdir:
            print_directory(path + "/" + file, tabs + 1)


# print("Files on filesystem:")
# print("====================")
# print_directory("/sd")

with open("/sd/ota.bin", "r") as f:
    print('flashing')
    data = f.read(10)
    print(data)
    dualbank.flash(data)
    print('done')
