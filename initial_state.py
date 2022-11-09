import json
import adafruit_logging as logging

try:
    from secrets import secrets
except ImportError:
    print("credentials are kept in secrets.py, please add them there!")
    raise

class Initial_state_streamer():
    def __init__(self, requests):
        
        self.requests = requests

        bucket_key = secrets["bucket_key"]
        access_key = secrets ["access_key"]

        self.url = 'https://groker.init.st/api/events'
        self.headers = {
            'Content-Type': 'application/json',
            'X-IS-AccessKey': access_key,
            'X-IS-BucketKey': bucket_key,
            'Accept-Version': '~0'
        }

    def send_data(self, datadict):

        output = []
        for key, value in datadict.items():
            datapoint = {
                "key"   : key,
                "value" : value,
            }
            output.append(datapoint)

        r = self.requests.post(self.url, data=json.dumps(output), headers=self.headers)
        print(f'{r.status_code=}')  
        print(f'{r.text=}')