import time
import adafruit_logging as logging
import rtc
import traceback
import microcontroller
from watchdog import WatchDogTimeout

# https://github.com/blues/note-python
import notecard
from notecard import hub, card, file, note, env

from secrets import secrets, notecard_config


class Notecard_manager():
    def __init__(self, loghandler=None, i2c=None, debug=False, loglevel=logging.INFO, watchdog=False):
        try:
            # Set up logging
            self.log = logging.getLogger('notecard')
            self.log.setLevel(loglevel)

            self.ncard=None

            if i2c:
                self.ncard = notecard.OpenI2C(i2c, 0, 0, debug=debug)
            else:
                self.log.critical('an I2C bus must be provided')

            if loghandler:
                self.log.addHandler(loghandler)
                loghandler.aux_log_function = self.log_function

            self.display("Starting Notecard Manager")

            # Real Time Clock in ESP32-S2 can be used to track timestamps
            self.rtc = rtc.RTC()

            self.mode = "continuous"

            self.environment = {}
            self.env_stamp = 0 #posix time of last update from notehub

            self.inbound_notes = {'data.qi'  : None}

            self.timestamped_note = {}
            self.timestamped_log = {}

            self.connected = False
            self.last_sync = 0

            self.check_config()
            self.wait_for_time()
            self.sync_time()

            if watchdog:
                # start a watchdog timer
                # Will pull ATTN pin low for 5s if no activity detected for "seconds"
                # seconds must be >=60
                # ATTN should be connected to e.g. Feather_en using switch on notecarrier.
                # Currently not working with notecard FW 3.x.x
                # https://discuss.blues.io/t/watchdog-not-triggering/1067/5
                card.attn(self.ncard, mode="watchdog", seconds=watchdog)
        except Exception as e:
            self.handle_exception(e)
            self.log.error("Could not initialise Notecard")

    def check_config(self):

        config_ok = True 
        self.log.info("Checking notecard settings match the notecard_config in secrets.py")

        hubget = hub.get(self.ncard)

        if "product" in hubget:
            if hubget["product"] != notecard_config["productUID"]:
                self.log.warning(f"Notecard productUID {hubget['product']} doesn't match {notecard_config['productUID']}")
                config_ok = False
        else:
            config_ok = False

        for setting in ['inbound', 'outbound', 'sync', 'mode']:
            if setting in hubget:
                if hubget[setting] != notecard_config[setting]:
                    self.log.warning(f"Notecard setting {hubget[setting]} doesn't match {notecard_config[setting]}")
                    config_ok = False

        # wifi
        req = {"req": "card.wifi"}
        cardwifi = self.ncard.Transaction(req)

        if "ssid" in cardwifi:
            if cardwifi["ssid"] != secrets["ssid"]:
                self.log.warning(f"Notecard SSID {cardwifi['ssid']} doesn't match {secrets['ssid']}")
                config_ok = False
                
        if config_ok == False:
            self.log.warning('Reconfiguring Notecard in 15s')
            time.sleep(15)
            self.reconfigure()
        else:
            self.log.info('Config OK')


    def check_status(self, nosync_timeout=None, nosync_warning=120):
        try:
            cstatus = card.status(self.ncard)
            self.log.debug(f"card.status={cstatus}")
            if "storage" in cstatus:
                percentage = cstatus["storage"]
                if percentage > 50:
                    self.log.info(f"notecard storage at {percentage}%")
            if "connected" in cstatus:
                self.connected = True
                return

            # Sync with 'allow' to avoid penalty boxes
            req = {"req": "hub.sync"}
            req['allow'] = True
            self.ncard.Transaction(req)

            self.connected = False
            t_since_sync = nosync_timeout
            self.last_sync = 0

            rsp = hub.syncStatus(self.ncard)
            self.log.debug(f"hub.syncStatus = {rsp}")
            self.display(str(rsp))
            time.sleep(2)
            if 'completed' in rsp:
                t_since_sync = rsp['completed']
            if 'requested' in rsp:
                t_since_sync = rsp['requested']
            if 'time' in rsp:
                self.last_sync = rsp['time']

            if nosync_warning:
                if t_since_sync >= nosync_warning:
                    self.log.debug(f"no sync in {t_since_sync}s")
            if nosync_timeout:        
                if t_since_sync >= nosync_timeout:
                    self.log.critical(f"no sync in {t_since_sync}s, timed out, reconfiguring notecard")
                    # microcontroller.reset()
                    self.reconfigure()
         
        except Exception as e:
            self.handle_exception(e)

    def wait_for_time(self):
        try:
            stamp = time.monotonic()
            while True:
                self.check_status(nosync_timeout=100)
                if self.connected:
                    self.log.info("connected")
                    break

                print(f'{self.last_sync=}')

                if self.last_sync > 0:
                    self.log.info(f'No connection, but time was set at {self.last_sync}')
                    break

                if time.monotonic() - stamp > 100:
                    stamp = time.monotonic()
                    self.log.critical("Timeout while waiting for notecard time, reconfiguring notecard")
                    self.reconfigure()

                time.sleep(1)

        except Exception as e:
            self.handle_exception(e)

    def sync_time(self):
        try:
            rsp = card.time(self.ncard)
            unixtime = rsp['time']
            self.rtc.datetime = time.localtime(unixtime)
            self.log.debug(f'RTC syncronised')
        except Exception as e:
            self.handle_exception(e)

    def set_default_envs(self, typed_env, clear=True):
        try:
            for key, val in typed_env.items():
                env.default(self.ncard, key, str(val))
                self.log.info(f'setting default environment: {key} = {val}')

            if clear:
                rsp = env.get(self.ncard)
                for key in rsp['body'].keys():
                    if key not in typed_env.keys() and key[0] != "_":
                        env.default(self.ncard, key)
                        self.log.warning(f'clearing default environment variable: {key}')

            hub.sync(self.ncard)
            self.receive_environment(typed_env)
        except Exception as e:
            self.handle_exception(e)

    def receive_environment(self, typed_env=None):
        try:

            modified = env.modified(self.ncard)
            if modified["time"] > self.env_stamp:
            
                self.log.debug("Updating Environment Variables")
                self.environment = {}
                
                rsp = env.get(self.ncard)
                self.environment = rsp["body"]
                self.env_stamp = modified["time"]
                self.log.debug(f"environment = {self.environment}")

                if typed_env is not None:
                    for key, val in self.environment.items():
                        if key in typed_env.keys():
                            try:
                                dtype = type(typed_env[key])
                                if dtype == list:
                                    if (val[0] == "[") and (val[-1] == "]"):
                                        typed_val = eval(val)
                                    else:
                                        print(f"Couldn't parse {val}, expected a list")
                                else:
                                    typed_val = dtype(val)

                                typed_env[key] = typed_val
                            except Exception as e:
                                    self.log.error(f"Could not parse {key} = {val}, {e}")
                            self.log.debug(f"environment update: {key} = {typed_val}")
                        elif key[0] != "_":
                            typed_env[key] = val
                            self.log.debug(f"environment update: {key} = {val} *unknown type*")
                return True
            else:
                # No update
                return False
        except Exception as e:
            self.handle_exception(e)

    def receive_note(self, notefile="data.qi"):
        try:
            changes = file.changes(self.ncard)
            if notefile in changes['info']:
                if "total" in changes['info'][notefile]:
                    self.log.debug(f"Receiving {notefile}")
                    rsp = note.get(self.ncard, file=notefile, delete=True)
                    if "body" in rsp:
                        self.inbound_notes[notefile] = rsp["body"]
                        self.log.debug(f'{notefile} = {rsp["body"]}')
        except Exception as e:
            self.handle_exception(e)


    def send_timestamped_note(self, sync=True):
        try:
            if len(self.timestamped_note) > 0:
                rsp = note.add(self.ncard, file="data.qo", body=self.timestamped_note, sync=sync)
                if "err" in rsp:
                    self.log.warning(f'error sending note {self.timestamped_note}, {rsp["err"]=}')
                else:
                    self.log.debug(f'sent note {self.timestamped_note}')
                    self.timestamped_note = {}
        except Exception as e:
            self.handle_exception(e)

    def send_timestamped_log(self, sync=True):
        try:
            if len(self.timestamped_log) > 0:
                rsp = note.add(self.ncard, file="log.qo", body=self.timestamped_log, sync=sync)
                if "err" in rsp:
                    self.log.warning(f'error sending log {self.timestamped_log}, {rsp["err"]=}')
                else:
                    self.log.debug(f'sent log {self.timestamped_log}')
                    self.timestamped_log = {}
        except Exception as e:
            self.handle_exception(e)

    def add_to_timestamped_note(self, datadict):
        try:
            ts = time.mktime(self.rtc.datetime)
            self.timestamped_note[ts] = datadict.copy()
        except Exception as e:
            self.handle_exception(e)

    def add_to_timestamped_log(self, text, ts):
        try:
            if ts in self.timestamped_log:
                self.timestamped_log[ts].append(text)
            else:
                self.timestamped_log[ts] = [text]
        except Exception as e:
            self.handle_exception(e)

    def send_note(self, datadict, file="data.qo", sync=True):
        try:
            note.add(self.ncard, file=file, body=datadict, sync=sync)
            self.log.debug(f'sending note {datadict}')
        except Exception as e:
            self.handle_exception(e)

    def log_function(self, record):
        # Intended to be used with the mcu library's loghandler
        # connect at the top level with e.g.
        # mcu.loghandler.aux_log_function = ncm.log_function

        t = self.rtc.datetime
        ts = f'{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} {t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}'
        text = f'{record.name} {record.levelname} {record.msg}'

        if record.levelno >= logging.WARNING:
            self.send_note({ts: text}, file="log.qo")

        if record.levelno >= logging.INFO:
            self.add_to_timestamped_log(text, ts)

    def reconfigure(self):
        try:
            # req = {"req": "card.restore"}
            # req["delete"] = False
            # req["connected"] = False
            # self.ncard.Transaction(req)

            hub.set(self.ncard, 
                product=notecard_config['productUID'],
                mode=notecard_config['mode'],
                sync=notecard_config['sync'],
                outbound=notecard_config['outbound'],
                inbound=notecard_config['inbound'])        


            # If it is a wifi notecard, set up SSID/Password
            req = {"req": "card.version"}
            cardversion = self.ncard.Transaction(req)
            if 'sku' in cardversion:
                if cardversion['sku'] == "NOTE-WIFI":
                    req = {"req": "card.wifi"}
                    req["ssid"] = secrets['ssid']
                    req["password"] = secrets['password']
                    rsp = self.ncard.Transaction(req)

            req = {"req": "card.restart"}
            self.ncard.Transaction(req)
            self.log.info('restarting Notecard, waiting 20s')
            time.sleep(20)
        except Exception as e:
            self.handle_exception(e)

    def display(self, message):
        # Special log command with custom level, to request sending to attached display
        self.log.log(level=25, msg=message)

    def handle_exception(self, e):
        cl = e.__class__
        if cl == OSError:
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.warning("{cl} {e}, Notecard restarting, or i2c bus issue, too many pullups?")
            time.sleep(1)
        else:
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.critical(f"Unhandled Notecard Error, Raising")
            raise e


