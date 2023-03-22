import time
from circuitpy_mcu.notecard_manager import Notecard_manager

import board
import busio

import adafruit_mcp9600
import supervisor

__version__ = "0.1.0"

env = {
    'sample_interval'         : 1, #minutes
    'note-send-interval'      : 5, #minutes
    }

notecard_config = {
    'productUID' : 'dwt.ac.uk.portable_sensor',
    'mode'       : 'periodic',
    'inbound'    : env['note-send-interval'],
    'outbound'   : env['note-send-interval'],
    }

def connect_thermocouple_channels():
    tc_addresses = [0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67]
    tc_channels = []

    for addr in tc_addresses:
        try:
            tc = adafruit_mcp9600.MCP9600(i2c, address=addr)
            tc_channels.append(tc)
            print(f'Found thermocouple channel at address {addr:x}')
            
        except Exception as e:
            print(f'No thermocouple channel at {addr:x}')

    return tc_channels

i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
ncm = Notecard_manager(i2c=i2c, watchdog=120, synctime=False, config_dict=notecard_config)

ncm.set_default_envs(env, sync=False)
ncm.receive_environment(env)
ncm.set_sync_interval(inbound=env['note-send-interval'], outbound=env['note-send-interval'])

tc_channels = connect_thermocouple_channels()
data = {}
for tc in tc_channels:
    i = tc_channels.index(tc)
    data[f'tc{i+1}'] = tc.temperature

ncm.send_note(data, sync=False)
print(data)

# TRY testing the watchdog here!

next_sample_countdown = env['sample_interval'] * 60
print(f"about to sleep for {next_sample_countdown}s")
ncm.sleep_mcu(seconds=next_sample_countdown)

# Pretend to power down when USB still connected
time.sleep(next_sample_countdown)
supervisor.reload()