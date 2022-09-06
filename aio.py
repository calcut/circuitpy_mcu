
# System and timing
import time
import rtc
import adafruit_logging as logging
import traceback
import microcontroller

import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_HTTP, IO_MQTT, AdafruitIO_RequestError, validate_feed_key
from adafruit_io.adafruit_io_errors import AdafruitIO_ThrottleError, AdafruitIO_MQTTError
import ssl

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/calcut/circuitpy-mcu"

class Aio_http(IO_HTTP):
    '''
    A wrapper for IO_HTTP providing MQTT like behaviour with subscriptions
    '''

    def __init__(self, requests, group='Default', loghandler=None, ota=True):

        self.requests = requests
        self.group = group
        username=secrets["aio_username"]
        password=secrets["aio_key"]

        super().__init__(username, password, self.requests)

        # Initialise some key variables
        self.subscribed_feeds = {} # a dict to showing which feeds to pull via http, including last update time
        self.updated_feeds = {} # a list of recently modified feeds, for ready for parsing.
        self.interval_minimum = 2 #Just an initial value, will be updated in code
        self.throttled = False

        self.timer_publish = time.monotonic()
        self.timer_throttled = time.monotonic()
        self.timer_receive = 0

        # Set up logging
        self.log = logging.getLogger('aio_http')
        if loghandler:
            self.log.addHandler(loghandler)

        # Real Time Clock in ESP32-S2 can be used to track timestamps
        self.rtc = rtc.RTC()
        self.time_sync()

        # Setup default group and feeds
        self.create_and_get_group(self.group)
        if ota:
            self.subscribe('ota')
        if loghandler:
            self.create_and_get_feed('log')


    def create_and_get_group(self, group_key):
        try:
            return self.get_group(f'{group_key}')
        except AdafruitIO_RequestError as e:
            cause = e.args[0]
            if cause[18:21] == '404':
                self.log.warning(f'{group_key} not found, creating')
                self.create_new_group(group_key, None)
                return self.get_group(f'{group_key}')
            else:
                self.handle_exception(e)
        except Exception as e:
            self.handle_exception(e)


    def create_and_get_feed(self, feed_key, detailed=False, feed_desc=None, feed_license=None):
            try:
                return self.get_feed(f'{self.group}.{feed_key}')
            except AdafruitIO_RequestError as e:
                cause = e.args[0]
                if cause[18:21] == '404':
                    self.log.info(f'{feed_key} not found in {self.group}, creating')
                    self.create_feed_in_group(self.group, feed_key)
                    return self.get_feed(f'{self.group}.{feed_key}')
                else:
                    self.handle_exception(e)
            except Exception as e:
                self.handle_exception(e)

    def handle_exception(self, e):
        # formats an exception to print to log as an error,
        # includues the traceback (to show code line number)
        self.log.error(traceback.format_exception(None, e, e.__traceback__))

        cl = e.__class__
        if cl == RuntimeError:
            self.log.warning('runtime error, try reconnecting wifi? or hard reset')
            # raise ConnectionError(f"AIO runtime error {e}")
            microcontroller.reset()

        elif cl == AdafruitIO_ThrottleError:
            self.interval_minimum += 1
            self.throttled = True
            self.timer_throttled = time.monotonic()
            self.log.warning(f'AIO Throttled, increasing publish interval to {self.interval_minimum}')

        elif cl == AdafruitIO_RequestError:
            cause = e.args[0]
            print(f'{cause=}')

        else:
            self.log.warning('Unhandled AIO exception, performing hard reset')
            # raise ConnectionError(f"Unhandled AIO Exception {e}")
            microcontroller.reset()

    def time_sync(self):
        try:
            unixtime = self.requests.get('https://io.adafruit.com/api/v2/time/seconds').text
            self.rtc.datetime = time.localtime(int(unixtime[:10]))
            self.log.info(f'RTC syncronised')

        except Exception as e:
            self.handle_exception(e)


    def receive(self, interval=10):
        # Recommend not subscribing to many feeds as it could slow down performance a lot.
        # Intended to be called in a loop, but will limit itself to a period of 'interval' seconds

        if self.throttled:
            if (time.monotonic() - self.timer_throttled) >= 30:
                # Reset the throttled flag if it has been over 30s
                self.throttled = False
                self.log.warning(f'AIO throttle flag released. minimum interval currently {self.interval_minimum}')

        if time.monotonic() - self.timer_receive > interval:
            self.timer_receive = time.monotonic()

            try:
                for key in self.subscribed_feeds.keys():

                    feed = self.create_and_get_feed(key)

                    # Determine if feed has been updated since last receive   
                    tm_str = feed["updated_at"]
                    time_tuple = (int(tm_str[0:4]),
                                  int(tm_str[5:7]),
                                  int(tm_str[8:10]), 
                                  int(tm_str[11:13]),
                                  int(tm_str[14:16]),
                                  int(tm_str[17:19]),
                                  -1, -1, -1)

                    this_update = time.struct_time(time_tuple)

                    # Maintain a list of recently modified feeds, for ready for parsing.
                    try:
                        previous_update = self.subscribed_feeds[key]["updated_at"]

                        if this_update > previous_update:
                            self.updated_feeds[key] = feed["last_value"]
                            self.log.info(f'updated_feeds["{key}"] = {feed["last_value"]}')

                    except TypeError:
                        self.log.debug('No previous value found')

                    self.subscribed_feeds[key] = {
                        "last_value" : feed["last_value"],
                        "updated_at" : this_update
                    }

            except Exception as e:
                self.handle_exception(e)

        return len(self.updated_feeds)

    def subscribe(self, feed_key):
        # Subscribe to a feed from Adafruit IO
        try:
            feed = self.create_and_get_feed(feed_key)
             
            tm_str = feed["updated_at"]
            time_tuple = (int(tm_str[0:4]),
                            int(tm_str[5:7]),
                            int(tm_str[8:10]), 
                            int(tm_str[11:13]),
                            int(tm_str[14:16]),
                            int(tm_str[17:19]),
                            -1, -1, -1)

            this_update = time.struct_time(time_tuple)
            self.subscribed_feeds[feed_key] = {
                    "last_value" : feed["last_value"],
                    "updated_at" : this_update
                }
            self.log.info(f'added {feed_key} to subscribed_feeds')
        except Exception as e:
            self.handle_exception(e)

    def publish_long(self, feed_key, feed_data):

        if not self.throttled:
            chunks = []
            while (len(feed_data) > 1023):
                chunks.append(feed_data[:1023])
                feed_data = feed_data[1023:]
            chunks.append(feed_data[:1023])
            self.log.info(f"Publishing data to AIO in {len(chunks)} chunks")

            try:
                full_name = f'{self.group}.{feed_key}'
                for c in chunks:
                    self.send_data(full_name, c)

            except AdafruitIO_RequestError as e:
                cause = e.args[0]
                if cause[18:21] == '404':
                    self.log.warning(f'{feed_key} not found in {self.group}, creating')
                    self.create_feed_in_group(self.group, feed_key)
                    self.send_data(full_name, c)
                else:
                    self.handle_exception(e)

            except Exception as e:
                self.handle_exception(e)

    def publish_feeds(self, feeds, location=None, interval=30):
        '''
        sends a dictionary of feeds to AIO, one by one.
        '''
        if not self.throttled:

            # Clamp the minimum interval based on number of feeds and a
            # rate of 30 updates per minute for AIO free version.
            if interval < self.interval_minimum:
                self.log.warning(f'publish interval clamped to {self.interval_minimum}s due to throttling')
                interval = self.interval_minimum

            if (time.monotonic() - self.timer_publish) >= interval:
                self.timer_publish = time.monotonic()

                self.log.info(f"Publishing to AIO:")
                for feed_key in sorted(feeds):
                    try:
                        full_name = f'{self.group}.{feed_key}'
                        data = str(feeds[feed_key])
                        self.send_data(full_name, data, metadata=location)
                        self.log.info(f"{feeds[feed_key]} --> {full_name}")

                    except AdafruitIO_RequestError as e:
                        cause = e.args[0]
                        if cause[18:21] == '404':
                            self.log.warning(f'{feed_key} not found in {self.group}, creating')
                            self.create_feed_in_group(self.group, feed_key)
                            self.send_data(full_name, data, metadata=location)
                        else:
                            self.handle_exception(e)

                    except Exception as e:
                        self.handle_exception(e)
                        self.log.error(f"Error publishing data to AIO")

                if location:
                    self.log.info(f"with location = {location}")

            else:
                self.log.debug(f"Waiting to publish, interval set to {interval}s"
                                +f" Time remaining: {int(interval - (time.monotonic() - self.timer_publish))}s")
        else:
            self.log.warning(f'Did not publish, throttled flag = {self.throttled}')
            

class Aio_mqtt():
    '''
    A custom implementation comparable to IO_MQTT, but

    OTA, RTC features
    fixed group for all feeds

    a dict called "updated_feeds" to store incoming feeds

    '''

    def __init__(self, pool, group='Default', loghandler=None):

        # Initialize a new MQTT Client object
        mqtt_client = MQTT.MQTT(
            broker="io.adafruit.com",
            username=secrets["aio_username"],
            password=secrets["aio_key"],
            socket_pool=pool,
            ssl_context=ssl.create_default_context()
        )

        self.client = mqtt_client
        self.group = group
        self._user = secrets["aio_username"]


        # MQTT event callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        self.client.on_unsubscribe = self.on_unsubscribe
        self.connected = False

        # Initialise some key variables
        self.updated_feeds = {} # a list of recently modified feeds, for ready for parsing.
        self.interval_minimum = 2 #Just an initial value, will be updated in code
        self.throttled = False

        self.timer_publish = time.monotonic()
        self.timer_throttled = time.monotonic()
        self.timer_receive = 0

        # Set up logging
        self.log = logging.getLogger('aio_mqtt')
        if loghandler:
            self.log.addHandler(loghandler)

        # Real Time Clock in ESP32-S2 can be used to track timestamps
        self.rtc = rtc.RTC()
        self.client.connect()

    def on_connect(self, client, userdata, flags, return_code):
        # Connected function will be called when the client is connected to Adafruit IO.
        # This is a good place to subscribe to feed changes.  The client parameter
        # passed to this function is the Adafruit IO MQTT client so you can make
        # calls against it easily.
        self.connected = True
        print("Connected to AIO")
        # self.log.info("Connected to AIO")
        self.display("Connected to AIO")
        self.client.subscribe(f"{self._user}/throttle")
        self.client.subscribe(f"{self._user}/errors")
        self.subscribe(f"ota", get_latest=False) #Listen for requests for over the air updates

    def on_subscribe(self, client, user_data, topic, granted_qos):
        print(f"Subscribed to {topic} with QOS level {granted_qos}")
        # self.log.info(f"Subscribed to {topic} with QOS level {granted_qos}")
        # Not using logger in this callback, as errors were seen eg.
        # AdafruitIO_MQTTError: MQTT Error: Unable to connect to Adafruit IO.
        # Possibly related to logging to SD card taking too long?
        # May also get "pystack exausted" if trying to do too much in callbacks

    def on_unsubscribe(self, client, user_data, topic, pid):
        """Runs when the client calls on_unsubscribe."""
        print(f'Unsubscribed from {topic}')
        # self.log.info(f'Unsubscribed from {topic}')

    def on_disconnect(self, client, userdata, return_code):
        self.connected = False
        print('AIO disconnected')
        # self.log.info('AIO disconnected')

    def on_message(self, client, topic, payload):
        # Message function will be called when a subscribed feed has a new value.
        # The feed_id parameter identifies the feed, and the payload parameter has
        # the new value

        # Initial parsing to handle non-standard feed / topics
        topic_name = topic.split("/")
        if topic_name[1] == "groups":
            raise AdafruitIO_MQTTError('Groups currently not implemented')
        elif topic_name[1] == "throttle":
            raise AdafruitIO_ThrottleError(payload)
        elif topic_name[0] == "time":
            feed_id = topic_name[1]
            message = payload
        else:
            feed_id = topic_name[2]
            message = payload
            
        # General parsing 
        if feed_id == 'seconds':
            self.rtc.datetime = time.localtime(int(message))
            print('RTC Synchronised')

        elif feed_id == f"{self.group}.ota":
            self.log.warning(f'got OTA request {payload}')
            self.log.warning(f'got OTA request {payload}')
            self.ota_requested = True # Can't fetch OTA in a callback, causes SSL errors.
        else:
            print(f"{feed_id} = {message}")
            # self.log.info(f"{feed_id} = {message}")
            self.updated_feeds[feed_id] = message

    def add_feed_callback(self, feed_key, callback_method):
        """Attaches a callback_method to an Adafruit IO feed.
        The callback_method function is called when a
        new value is written to the feed.

        NOTE: The callback_method registered to this method
        will only execute during loop().

        :param str feed_key: Adafruit IO feed key.
        :param str callback_method: Name of callback method.
        """
        validate_feed_key(feed_key)
        self.client.add_topic_callback(
            f"{self._user}/f/{self.group}.{feed_key}", callback_method
        )

    def remove_feed_callback(self, feed_key):
        """Removes a previously registered callback method
        from executing whenever feed_key receives new data.

        After this method is called, incoming messages
        call the shared on_message.

        :param str feed_key: Adafruit IO feed key.
        """
        validate_feed_key(feed_key)
        self.client.remove_topic_callback(f"{self._user}/f/{self.group}.{feed_key}")

    def sync(self, data_dict=None, loop_timeout=0, publish_interval=10):
        if self.connected:
            if self.throttled:
                if (time.monotonic() - self.timer_throttled) >= 30:
                    # Reset the throttled flag if it has been over 30s
                    self.throttled = False
                    self.log.warning(f'Throttle flag released. minimum interval currently {self.interval_minimum}')
            try:
                self.client.loop(loop_timeout)
                if data_dict:
                    self.publish_feeds(data_dict, location=None, interval=publish_interval)
            except Exception as e:
                self.handle_exception(e)

    def publish(self, feed_key, data, metadata=None):
        
        validate_feed_key(feed_key)
        if metadata is not None:
            csv_string = f"{data},{metadata}"
            self.client.publish(
                f"{self._user}/f/{self.group}.{feed_key}/csv", csv_string
            )
        else:
            self.client.publish(f"{self._user}/f/{self.group}.{feed_key}", data)   

    def publish_feeds(self, feeds, location=None, interval=10):
        '''
        sends a dictionary of feeds to AIO, one by one.
        '''
        if self.connected:
            if not self.throttled:
                if interval < self.interval_minimum:
                    self.log.warning(f'publish interval clamped to {self.interval_minimum}s due to throttling')
                    interval = self.interval_minimum

                if (time.monotonic() - self.timer_publish) >= interval:
                    self.timer_publish = time.monotonic()
                    self.log.info(f"Publishing to AIO:")
                    try:
                        for feed_id in sorted(feeds):
                            if self.group:
                                full_name = f'{self.group}.{feed_id}'
                            else:
                                full_name = feed_id
                            self.publish(full_name, str(feeds[feed_id]), metadata=location)
                            self.log.info(f"{feeds[feed_id]} --> {full_name}")
                        if location:
                            self.log.info(f"with location = {location}")
                    except Exception as e:
                        self.handle_exception(e)
                else:
                    self.log.debug(f"Did not publish, interval set to {interval}s"
                                    +f" Time remaining: {int(interval - (time.monotonic() - self.timer_publish))}s")
            else:
                self.log.warning(f'Did not publish, throttled flag = {self.throttled}')
        else:
            self.log.warning(f"AIO not connected")

    def publish_long(self, feed_key, feed_data):

        if not self.throttled:
            chunks = []
            while (len(feed_data) > 1023):
                chunks.append(feed_data[:1023])
                feed_data = feed_data[1023:]
            chunks.append(feed_data[:1023])
            self.log.info(f"Publishing data to AIO in {len(chunks)} chunks")
            try:
                for c in chunks:
                    self.send_data(feed_key, c)
            except Exception as e:
                self.handle_exception(e)

    def subscribe(self, feed_key, get_latest=True):
        validate_feed_key(feed_key)
        feed = f"{self._user}/f/{self.group}.{feed_key}"
        self.client.subscribe(feed)

        # Request latest value from the feed
        if get_latest:
            self.get(feed_key)

    def unsubscribe(self, feed_key):
        validate_feed_key(feed_key)
        feed = f"{self._user}/f/{self.group}.{feed_key}"
        self.client.unsubscribe(feed)

    def send_data(self, feed_key, data, metadata=None, precision=None):
        """
        A method to mimic the http version of send_data
        """
        if precision:
            try:
                data = round(data, precision)
            except NotImplementedError as err:  # received a non-float value
                raise NotImplementedError(
                    "Precision requires a floating point value"
                ) from err
        self.publish(feed_key, data, metadata=metadata)

    def get(self, feed_key):
        """Calling this method will make Adafruit IO publish the most recent
        value on feed_key.
        https://io.adafruit.com/api/docs/mqtt.html#retained-values
        """
        validate_feed_key(feed_key)
        self.client.publish(f"{self._user}/f/{self.group}.{feed_key}/get", "\0")

    def time_sync(self):
        #This will automatically unsubscribe after a successful RTC sync
        self.client.subscribe("time/seconds")
        time.sleep(1)
        self.client.unsubscribe("time/seconds")

    def display(self, message):
        # Special log command with custom level, to request sending to attached display
        self.log.log(level=25, msg=message)



    def handle_exception(self, e):
        # formats an exception to print to log as an error,
        # includues the traceback (to show code line number)
        self.log.error(traceback.format_exception(None, e, e.__traceback__))

        cl = e.__class__
        if cl == RuntimeError:
            self.log.warning('runtime error, try reconnecting wifi? or hard reset')
            # raise ConnectionError(f"AIO runtime error {e}")
            microcontroller.reset()

        elif cl == AdafruitIO_ThrottleError:
            self.interval_minimum += 1
            self.throttled = True
            self.timer_throttled = time.monotonic()
            self.log.warning(f'AIO Throttled, increasing publish interval to {self.interval_minimum}')

        elif cl == IndexError:
            self.log.error(f'AIO feed limit may have been reached')

        else:
            self.log.warning('Unhandled AIO exception, performing hard reset')
            # raise ConnectionError(f"Unhandled AIO Exception {e}")
            microcontroller.reset()





  