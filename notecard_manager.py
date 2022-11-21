import time
import adafruit_logging as logging
import rtc
import traceback
import microcontroller

# https://github.com/blues/note-python
import notecard
from notecard import hub, card, file, note, env

from secrets import secrets


class Notecard_manager():
    def __init__(self, loghandler=None, i2c=None, debug=False, loglevel=logging.INFO, watchdog=False):
        try:
            # Set up logging
            self.log = logging.getLogger('notecard')
            self.log.setLevel(loglevel)
            if loghandler:
                self.log.addHandler(loghandler)
                loghandler.aux_log_function = self.log_function

            if i2c:
                self.ncard = notecard.OpenI2C(i2c, 0, 0, debug=debug)
            else:
                self.log.critical('an I2C bus must be provided')

            self.display("Starting Notecard Manager")

            # Real Time Clock in ESP32-S2 can be used to track timestamps
            self.rtc = rtc.RTC()

            self.mode = "continuous"

            self.environment = {}
            self.env_stamp = 0 #posix time of last update from notehub

            self.inbound_notes = {'data.qi'  : None}

            self.timestamped_note = {}
            self.timestamped_log = {}

            self.wait_for_conection()
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
        
    def wait_for_conection(self):
        try:
            stamp = time.monotonic()
            while True:
                try:
                    status = card.status(self.ncard)
                    if "connected" in status:
                        break

                    else:
                        # check details of connection status
                        rsp = hub.syncStatus(self.ncard)
                        # if not debug:
                        self.log.debug(f"{rsp['status']}")
                        self.display(f"{rsp['status']}")

                    if time.monotonic() - stamp > 100:
                        stamp = time.monotonic()
                        self.log.warning('no connection, reconfiguring notecard')
                        self.reconfigure()

                    
                except OSError as e:
                    # notecard may be rebooting
                    print(e)

                time.sleep(1)

            self.log.debug("connected")
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

            hub.set(self.ncard, product=secrets['productUID'], mode=self.mode, sync=True, outbound=2, inbound=2)        

            req = {"req": "card.wifi"}
            req["ssid"] = secrets['ssid']
            req["password"] = secrets['password']
            rsp = self.ncard.Transaction(req)

            req = {"req": "card.restart"}
            self.ncard.Transaction(req)
        except Exception as e:
            self.handle_exception(e)

    def display(self, message):
        # Special log command with custom level, to request sending to attached display
        self.log.log(level=25, msg=message)

    def handle_exception(self, e):
        cl = e.__class__
        if cl == OSError:
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.warning("{cl} {e}, likely i2c bus issue, too many pullups?")
        else:
            self.log.error(traceback.format_exception(None, e, e.__traceback__))
            self.log.critical(f"Unhandled Notecard Error, Hard resetting in 10s")
            time.sleep(10)
            microcontroller.reset()


