import time
from circuitpy_mcu.notecard_manager import Notecard_manager
from circuitpy_mcu.mcu import McuLogHandler

import board
import busio

import adafruit_mcp9600
import supervisor

__version__ = "0.1.0"

env = {
    'sample_interval'         : 1, #minutes
    'hub-sync-interval'      : 1, #minutes
    }

notecard_config = {
    'productUID' : 'dwt.ac.uk.portable_sensor',
    'mode'       : 'periodic',
    }

uart = busio.UART(board.TX, board.RX, baudrate=115200)
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)

# Using this loghandler simplifies printing to UART, useful for debug without USB power
loghandler = McuLogHandler(uart=uart)
ncm = Notecard_manager(i2c=i2c, watchdog=60, synctime=False, config_dict=notecard_config, loghandler=loghandler)

# Don't want to send logs to notehub in this application
loghandler.aux_log_function = None

ncm.set_default_envs(env, sync=False)
ncm.set_sync_interval(inbound=env['hub-sync-interval'], outbound=env['hub-sync-interval'])

# Connect up to 8 thermocouple amp boards
tc_addresses = [0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67]
tc_channels = []

for addr in tc_addresses:
    try:
        tc = adafruit_mcp9600.MCP9600(i2c, address=addr)
        tc_channels.append(tc)
        ncm.log.info(f'Found thermocouple channel at address {addr:x}')
        
    except Exception as e:
        ncm.log.info(f'No thermocouple channel at {addr:x}')

# Read the thermocouple channels
data = {}
for tc in tc_channels:
    i = tc_channels.index(tc)
    data[f'tc{i+1}'] = tc.temperature

# Send the data to the notecard
ncm.send_note(data, sync=False)
ncm.log.info(f'Sent note containing: {data}')

next_sample_countdown = env['sample_interval'] * 60
ncm.log.info(f"about to sleep for {next_sample_countdown}s")
ncm.sleep_mcu(seconds=next_sample_countdown)

# Pretend to power down when USB still connected
time.sleep(next_sample_countdown)
supervisor.reload()


