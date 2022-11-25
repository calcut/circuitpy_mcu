import json

try:
    from secrets import secrets
except ImportError:
    print("credentials are kept in secrets.py, please add them there!")
    raise

class Initial_state_streamer():
    def __init__(self, requests, bucket_key=None, access_key=None):
        
        self.requests = requests

        if bucket_key is None:
            bucket_key = secrets["bucket_key"]
        if access_key is None:
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
        # print(f'{r.status_code=}')  
        # print(f'{r.text=}')