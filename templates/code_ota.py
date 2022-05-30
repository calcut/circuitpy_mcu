import supervisor
import microcontroller
from watchdog import WatchDogTimeout
import traceback
import time
from circuitpy_mcu.ota_bootloader import Bootloader

# code = '/circuitpy_septic_tank/septic_tank.py'
# code = '/circuitpy_iot_sensor/iot_sensor.py'
# code = '/circuitpy_mcu/ota_test.py'
# code = '/circuitpy_septic_tank/methane_gascard.py'
# code = '/circuitpy_septic_tank/pump.py

supervisor.disable_autoreload()

OTA_LIST_URL = 'https://raw.githubusercontent.com/calcut/circuitpy_septic_tank/main/ota_list.py'

try:
    bl = Bootloader(watchdog_timeout=20)
    bl.wifi_connect()
    bl.get_ota_list(OTA_LIST_URL)        
    code = "/circuitpy_septic_tank/septic_tank.py"
    supervisor.set_next_code_file(code, reload_on_success=False)
    supervisor.reload()

except KeyboardInterrupt:
    print('Code Stopped by Keyboard Interrupt')
    # May want to add code to stop gracefully here 
    # e.g. turn off relays or pumps

except WatchDogTimeout:
    print('Code Stopped by WatchDog Timeout!')
    print('Performing hard reset in 15s')
    time.sleep(15)
    microcontroller.reset()

except Exception as e:
    print(f'Code stopped by unhandled exception:')
    print(traceback.format_exception(None, e, e.__traceback__))
    # Can we log here?
    print('Performing a hard reset in 15s')
    time.sleep(15) #Make sure this is shorter than watchdog timeout
    # supervisor.reload()
    microcontroller.reset()


"""
Bootloader

Determine if read only?
By reading pin value?
or by trying to write?



if writable:

    Connect to internet
    Get OTA list
    check version
    Run
    possibly reboot once a day to mitigate getting locked out.


if not writable

if not available, run default

Can I import file just downloaded?






"""