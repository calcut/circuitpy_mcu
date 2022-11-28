
# Example secrets file, rename to secrets.py and populate as required.

secrets = {

# Wifi Credentials
    'ssid' : 'xxx',
    'password' : 'xxxx',

    'timezone' : 'Europe/London',

}

notecard_config = {
    'productUID' : 'mynotehubPID:XXXXXX',
    'mode'       : 'continuous',
    # 'mode'       : 'periodic',
    'sync'       : True,
    'inbound'    : 2,
    'outbound'   : 2,
}