import time
from circuitpy_mcu.reset import reset
from circuitpy_mcu.notecard_manager import Notecard_manager
from circuitpy_mcu.mcu import Mcu_swan
import adafruit_logging as logging
import adafruit_mcp9600
import supervisor
from notecard import hub, card, file, note, env

__version__ = "0.1.0"
__filename__ = "datalogger_battery.py"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

LOGLEVEL = logging.DEBUG

def main():

    # log = logging.getLogger('datalogger')
    # log.setLevel(LOGLEVEL)

    # set defaults for environment variables, (may be overridden by notehub)
    env = {
        'sample_interval'         : 1, #minutes
        'note-send-interval'      : 5, #minutes
        }
    
    i2c_dict = {
        '0x17' : 'BluesWireless Notecard', 
        '0x60' : 'Thermocouple Amp MCP9600',
        }
    
    notecard_config = {
    'productUID' : 'dwt.ac.uk.portable_sensor',
    'mode'       : 'periodic',
    'inbound'    : env['note-send-interval'],
    'outbound'   : env['note-send-interval'],
}
    
    next_sample = None
    next_sample_countdown = 0
    timer_sample = time.monotonic()

    def connect_thermocouple_channels():
        tc_addresses = [0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67]
        tc_channels = []

        for addr in tc_addresses:
            try:
                tc = adafruit_mcp9600.MCP9600(mcu.i2c, address=addr)
                tc_channels.append(tc)
                mcu.log.info(f'Found thermocouple channel at address {addr:x}')
                
            except Exception as e:
                mcu.log.info(f'No thermocouple channel at {addr:x}')

        return tc_channels
    

    mcu = Mcu_swan(loglevel=LOGLEVEL)
    mcu.i2c_identify(i2c_dict)

    ncm = Notecard_manager(loghandler=mcu.loghandler, i2c=mcu.i2c, watchdog=120, loglevel=LOGLEVEL, synctime=False, config_dict=notecard_config)
    mcu.led.value = True
    mcu.log.info(f'STARTING {__filename__} {__version__}')


    ncm.set_default_envs(env, sync=False)
    ncm.receive_environment(env)
    ncm.set_sync_interval(inbound=env['note-send-interval'], outbound=env['note-send-interval'])

    tc_channels = connect_thermocouple_channels()
    for tc in tc_channels:
        i = tc_channels.index(tc)
        mcu.data[f'tc{i+1}'] = tc.temperature

    ncm.send_note(mcu.data, sync=False)
    print(mcu.data)

    next_sample_countdown = env['sample_interval'] * 60
    mcu.log.info(f"about to sleep for {next_sample_countdown}s")
    ncm.sleep_mcu(seconds=next_sample_countdown)
    time.sleep(next_sample_countdown)
    supervisor.reload()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('Code Stopped by Keyboard Interrupt')

    except Exception as e:
        print(f'Code stopped by unhandled exception:')
        reset(e)