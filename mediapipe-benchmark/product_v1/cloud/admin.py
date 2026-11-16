"""Technician-only OAuth tooling. Never copied with hub/app artifacts."""
import base64
import hashlib
import json
import os
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT = 'smart-rehab-hub'
DB = 'https://smart-rehab-hub-default-rtdb.asia-southeast1.firebasedatabase.app'
KEY = 'AIzaSyCIhOntftB7QlhPdrYNDX_DQtXY3MwL8VI'


class Admin:
    def __init__(self):
        self.token = subprocess.check_output(['gcloud', 'auth', 'print-access-token', '--account=hoangjamesforwork@gmail.com'], text=True, stderr=subprocess.DEVNULL).strip()

    def request(self, url, method='GET', value=None):
        headers = {'Authorization': 'Bearer ' + self.token, 'x-goog-user-project': PROJECT, 'Content-Type': 'application/json'}
        req = urllib.request.Request(url, data=json.dumps(value).encode() if value is not None else None, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except urllib.error.HTTPError as error:
            body = json.load(error)
            code = body.get('error', {}).get('message', '') if isinstance(body.get('error'), dict) else str(body.get('error', ''))
            # Errors should contain API codes only, never account response objects.
            raise RuntimeError(f'admin_http_{error.code}: {code[:180]}') from None

    def database(self, path, method='GET', value=None):
        return self.request(DB + '/' + path + '.json', method, value)

    def account(self, action, value):
        return self.request(f'https://identitytoolkit.googleapis.com/v1/projects/{PROJECT}/accounts:{action}', 'POST', value)

    def new_account(self, email, name, claims, private_path):
        private_path = Path(private_path)
        if private_path.exists():
            stored = json.loads(private_path.read_text())
            if stored['email'] != email:
                raise ValueError('existing_account_file_email_differs')
            return stored
        existing = self.account('lookup', {'email': [email]}).get('users', [])
        if existing:
            raise ValueError('Account already exists; do not reset password or overwrite its claims')
        password = secrets.token_urlsafe(30)
        result = self.request('https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=' + KEY, 'POST',
                              {'email': email, 'password': password, 'displayName': name, 'returnSecureToken': True})
        uid = result['localId']
        self.account('update', {'localId': uid, 'customAttributes': json.dumps(claims)})
        stored = {'uid': uid, 'email': email, 'password': password, 'api_key': KEY, 'database_url': DB}
        private_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(private_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as out: json.dump(stored, out, indent=2)
        return stored

    def deploy_rules(self, backup_directory):
        from .generate_rules import product_rules
        directory = Path(backup_directory)
        live = self.database('.settings/rules')
        filename = directory / ('rules-before-' + hashlib.sha256(json.dumps(live, sort_keys=True).encode()).hexdigest()[:12] + '.json')
        if not filename.exists(): filename.write_text(json.dumps(live, ensure_ascii=False, indent=2) + '\n')
        candidate = json.loads(json.dumps(live))
        candidate['rules']['rehab_v1'] = product_rules()
        # Check every original branch is preserved; only product namespace is replaced.
        assert {k:v for k,v in live['rules'].items() if k != 'rehab_v1'} == {k:v for k,v in candidate['rules'].items() if k != 'rehab_v1'}
        self.database('.settings/rules', 'PUT', candidate)
        actual = self.database('.settings/rules')
        if actual != candidate: raise RuntimeError('Rules readback differs')
        (directory / 'rules-deployed.json').write_text(json.dumps(actual, ensure_ascii=False, indent=2) + '\n')
        print('Product rules deployed and read back; all other branches preserved.')
