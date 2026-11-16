"""Firebase REST publisher with client ID tokens; never Admin credentials."""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from .storage import dumps

ROOT_PATH = 'demo_e2e_v1/sessions'
PRODUCTION_DB = 'https://smart-rehab-hub-default-rtdb.asia-southeast1.firebasedatabase.app'

def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Invalid session ID')
    return value

def request(url, value=None, method='POST', form=False, timeout=3):
    body = None if value is None else (urllib.parse.urlencode(value) if form else dumps(value)).encode()
    headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=timeout) as response:
            return json.loads(response.read() or 'null')
    except urllib.error.HTTPError as error:
        # Do not log URL, auth query, response body or passwords.
        raise RuntimeError(f'firebase_http_{error.code}') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('firebase_network_unavailable') from None

class FirebaseClient:
    def __init__(self, config):
        if any(k in config for k in ('private_key', 'client_email', 'service_account')):
            raise ValueError('Admin credentials forbidden on Pi')
        self.config = config
        self.base = config.get('database_url', PRODUCTION_DB).rstrip('/')
        self.emulator = config.get('emulator', False)
        if self.emulator:
            host = urllib.parse.urlparse(self.base)
            if host.scheme != 'http' or host.hostname not in ('127.0.0.1', 'localhost'):
                raise ValueError('Emulator must be loopback; tunnel explicitly if needed')
        elif self.base != PRODUCTION_DB:
            raise ValueError('Unexpected Firebase destination')
        self.token, self.refresh, self.expires, self.uid = None, None, 0, None

    def authenticate(self):
        if self.token and time.monotonic() < self.expires:
            return
        key = urllib.parse.quote(self.config['api_key'], safe='')
        if self.refresh and not self.emulator:
            result = request(f'https://securetoken.googleapis.com/v1/token?key={key}',
                             {'grant_type': 'refresh_token', 'refresh_token': self.refresh}, form=True)
            self.token, self.refresh = result['id_token'], result['refresh_token']
            self.expires = time.monotonic() + int(result['expires_in']) - 60
            self.uid = result['user_id']
        else:
            auth = 'http://127.0.0.1:9099/identitytoolkit.googleapis.com' if self.emulator else 'https://identitytoolkit.googleapis.com'
            result = request(f'{auth}/v1/accounts:signInWithPassword?key={key}', {
                'email': self.config['email'], 'password': self.config['password'], 'returnSecureToken': True}, timeout=10)
            self.token, self.refresh, self.uid = result['idToken'], result['refreshToken'], result['localId']
            self.expires = time.monotonic() + int(result['expiresIn']) - 60

    def put(self, path, value):
        if not re.fullmatch(r'[A-Za-z0-9_/-]+', path):
            raise ValueError('Unsafe database path')
        self.authenticate()
        query = {'auth': self.token}
        if self.emulator:
            query['ns'] = 'demo-smart-rehab'
        try:
            request(f'{self.base}/{path}.json?{urllib.parse.urlencode(query)}', value, 'PUT')
        except RuntimeError as error:
            if str(error) == 'firebase_http_401':
                self.expires = 0
            raise

class Publisher:
    def __init__(self, client, journal, session_id, clock=time.time, monotonic=time.monotonic):
        self.client, self.journal, self.clock = client, journal, clock
        self.session_id, self.monotonic = session_id, monotonic
        self.prefix = f'{ROOT_PATH}/{safe_id(session_id)}'
        self.lock, self.stop = threading.Lock(), threading.Event()
        self.latest = None
        self.last_sent = 0
        self.last_attempt = -float('inf')
        self.thread = None
        self.successes, self.failures = 0, 0
        self.pause_window = None
        self.fault_history = []
        self.pause_active = False

    def schedule_pause(self, after_s, duration_s=30):
        if after_s < 0 or duration_s <= 0:
            raise ValueError('Pause requires after >= 0 and duration > 0')
        start = self.monotonic() + after_s
        self.pause_window = (start, start + duration_s)

    def is_paused(self):
        now = self.monotonic()
        active = bool(self.pause_window and self.pause_window[0] <= now < self.pause_window[1])
        if active != self.pause_active:
            self.fault_history.append({'epoch_ms': round(self.clock()*1000), 'monotonic_s': now,
                                      'event': 'publisher_pause_started' if active else 'publisher_pause_ended',
                                      'kind': 'simulated_transport_pause_not_internet_disconnect'})
            self.pause_active = active
        return active

    def offer(self, value):
        if value.get('session_id') != self.session_id:
            raise ValueError('Wrong session offered to publisher')
        # Landmarks, images and raw frames deliberately excluded from network packets.
        allowed = ('schema_version', 'algorithm_version', 'session_id', 'exercise', 'sequence',
                   'sample_timestamp_ms', 'side', 'joint', 'angle', 'raw_angle', 'visibility',
                   'tracking_status', 'reason', 'form_status', 'reps', 'phase', 'source',
                   'frame_received_epoch_ms', 'inference_complete_epoch_ms', 'algorithm_complete_epoch_ms')
        packet = {k: value[k] for k in allowed if k in value}
        with self.lock:
            if self.latest is None or (packet['sequence'] > self.latest['sequence'] and
                    packet.get('sample_timestamp_ms', float('inf')) > self.latest.get('sample_timestamp_ms', -float('inf'))):
                self.latest = packet

    def send(self, suffix, value, durable=False):
        start = time.perf_counter()
        try:
            self.client.put(f'{self.prefix}/{suffix}', value)
            if durable:
                self.journal.acknowledge(suffix)
            self.successes += 1
            self.journal.record_send(suffix, True, (time.perf_counter()-start)*1000)
            return True
        except Exception as error:
            self.failures += 1
            # Only controlled error codes; never serialize arbitrary exception text.
            code = str(error) if re.fullmatch(r'firebase_[a-z0-9_]+', str(error)) else type(error).__name__
            self.journal.record_send(suffix, False, (time.perf_counter()-start)*1000, code)
            return False

    def step(self):
        if self.is_paused():
            return True
        now = self.clock()
        with self.lock:
            value = dict(self.latest) if self.latest else None
        if (value and value['sequence'] > self.last_sent and now-self.last_attempt >= .2
                and 0 <= now*1000-value['frame_received_epoch_ms'] < 2000):
            self.last_attempt = now
            value['timestamp'] = round(now*1000)
            if not self.send('latest', value):
                return False
            self.last_sent = value['sequence']
        pending = self.journal.pending()
        if pending:
            path, data = pending[0]
            return self.send(path, data, durable=True)
        return True

    def start(self):
        def work():
            delay = .05
            while not self.stop.is_set():
                delay = .05 if self.step() else min(max(delay*2, 1), 10)
                self.stop.wait(delay)
        self.thread = threading.Thread(target=work, name='firebase-publisher', daemon=True)
        self.thread.start()

    def close(self, timeout=4):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout)
        return not self.thread or not self.thread.is_alive()
