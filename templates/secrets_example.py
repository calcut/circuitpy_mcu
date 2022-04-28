
# Example secrets file, rename to secrets.py and populate as required.

secrets = {

# OTA details
    'git_user' : 'user',
    'git_repo' : 'repo',
    'ota_file' : 'file_to_be_updated.py',

# Default Wifi Credentials
    'ssid' : 'xxx',
    'password' : 'xxxx',

# Advanced Wifi Credentials, for code that can parse it
# Allows multiple networks to be stored, code should connect to the strongest
# one.
    'networks' : {
    #   'SSID'             : 'Password'
        'xxxxxx'           : 'xxxxxxxx',
        'xxxxxx'           : 'xxxxxxxx',
        'xxxxxx'           : 'xxxxxxxx',
        },

    'aio_username' : 'xxxxx',
    'aio_key' : 'xxxxxxxx',
    
    'timezone' : 'Europe/London',
}