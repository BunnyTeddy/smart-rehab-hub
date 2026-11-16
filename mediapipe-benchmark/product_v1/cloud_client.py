"""Product Firebase transport. Only device ID tokens are installed on a hub."""
import json
import http.client
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from integration_v1.transport import FirebaseClient, PRODUCTION_DB, request as auth_request
from .protocol import dumps, safe_id, ROOT


class Cloud:
    def __init__(self, config):
        self.client = FirebaseClient(config)
        self.lock = threading.RLock()
        self.http = threading.local()
        self.last_success = 0.0

    def token(self):
        with self.lock:
            if self.client.emulator and (not self.client.token or time.monotonic() >= self.client.expires):
                result = auth_request('http://127.0.0.1:19099/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=demo-key',
                    {'email': self.client.config['email'], 'password': self.client.config['password'], 'returnSecureToken': True})
                self.client.token, self.client.uid = result['idToken'], result['localId']
                self.client.expires = time.monotonic() + int(result['expiresIn']) - 60
            else:
                self.client.authenticate()
            return self.client.token

    def url(self, path, extra=None):
        if any(not p or safe_id(p) != p for p in path.split('/')):
            raise ValueError('invalid_database_path')
        query = {'auth': self.token(), **(extra or {})}
        if self.client.emulator:
            query['ns'] = 'demo-smart-rehab-product'
        return self.client.base + '/' + path + '.json?' + urllib.parse.urlencode(query)

    def request(self, method, path, value=None, timeout=3):
        body = None if value is None else dumps(value).encode()
        url = urllib.parse.urlsplit(self.url(path))
        # Keep one HTTPS connection per worker. Repeated TLS handshakes for idle
        # heartbeats otherwise consume a substantial part of the Spark quota.
        connection = getattr(self.http, 'connection', None)
        if connection is None:
            client = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
            connection = self.http.connection = client(url.hostname, url.port, timeout=timeout)
        connection.timeout = timeout
        if connection.sock:
            connection.sock.settimeout(timeout)
        try:
            connection.request(method, url.path + '?' + url.query, body=body,
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            encoded = response.read()
            if response.status >= 400:
                if response.status == 401:
                    with self.lock:
                        self.client.expires = 0
                raise RuntimeError(f'firebase_http_{response.status}')
            result = json.loads(encoded or 'null')
            self.last_success = time.monotonic()
            return result
        except (OSError, TimeoutError, http.client.HTTPException):
            connection.close()
            self.http.connection = None
            raise RuntimeError('firebase_network_unavailable') from None

    def get(self, path):
        return self.request('GET', path)

    def put(self, path, value):
        return self.request('PUT', path, value)

    def verify_patient(self, id_token):
        if not isinstance(id_token, str) or not 100 <= len(id_token) <= 10000:
            raise ValueError('invalid_patient_token')
        origin = 'http://127.0.0.1:19099/identitytoolkit.googleapis.com' if self.client.emulator else 'https://identitytoolkit.googleapis.com'
        url = origin + '/v1/accounts:lookup?key=' + urllib.parse.quote(self.client.config['api_key'])
        request = urllib.request.Request(url, data=dumps({'idToken': id_token}).encode(),
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                users = json.load(response).get('users', [])
        except (OSError, ValueError):
            raise ValueError('patient_verification_failed') from None
        if len(users) != 1 or users[0].get('disabled'):
            raise ValueError('patient_verification_failed')
        user = users[0]
        claims = json.loads(user.get('customAttributes', '{}'))
        if claims.get('role') not in (None, 'patient'):
            raise ValueError('patient_account_required')
        return safe_id(user['localId'])

    def patient_hub(self, id_token, uid):
        """Read the patient's own index using their verified ID token, never Admin."""
        query = {'auth': id_token}
        if self.client.emulator:
            query['ns'] = 'demo-smart-rehab-product'
        url = self.client.base + f'/{ROOT}/patientHub/{safe_id(uid)}.json?' + urllib.parse.urlencode(query)
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.load(response)
        except (OSError, ValueError):
            raise ValueError('patient_verification_failed') from None

    def commands(self, hub_id, stop, callback):
        """Bounded SSE command query; reconnections never revive expired commands."""
        path = f'{ROOT}/commands/{safe_id(hub_id)}'
        while not stop.is_set():
            try:
                extra = {'orderBy': '"created_at"', 'limitToLast': 20}
                req = urllib.request.Request(self.url(path, extra), headers={'Accept': 'text/event-stream'})
                with urllib.request.urlopen(req, timeout=12) as response:
                    event, lines = '', []
                    for raw in response:
                        if stop.is_set():
                            break
                        line = raw.decode().rstrip('\r\n')
                        if line.startswith('event:'):
                            event = line[6:].strip()
                        elif line.startswith('data:'):
                            lines.append(line[5:].strip())
                        elif not line:
                            if event in ('cancel', 'auth_revoked'):
                                with self.lock:
                                    self.client.expires = 0
                                break
                            if event in ('put', 'patch') and lines:
                                message = json.loads('\n'.join(lines))
                                data = message.get('data')
                                key = message.get('path', '/').strip('/')
                                if isinstance(data, dict):
                                    if key and '/' not in key and 'action' in data:
                                        callback(key, data)
                                    elif not key:
                                        for command_id, command in data.items():
                                            if isinstance(command, dict) and 'action' in command:
                                                callback(command_id, command)
                            event, lines = '', []
            except (OSError, ValueError, RuntimeError):
                pass
            stop.wait(2)
