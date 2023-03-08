import microcontroller
import traceback
import supervisor
import time

def reset(exception=None):
    if exception:
        detail = traceback.format_exception(None, exception, exception.__traceback__)
        print(detail)
        try:
            with open('log_exception.txt', 'a') as f:
                f.write(detail)
                print('logged exception to /log_exception.txt')

        except Exception as e:
                print(f'Unable to save exception details, {e}')

    if supervisor.runtime.usb_connected:
        print('USB connected, performing soft reset in 15s')
        time.sleep(15)
        supervisor.reload()
    else:
        print('Performing a hard reset')
        microcontroller.reset()