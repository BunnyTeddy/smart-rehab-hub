"""Static Firebase Hosting deployment with a saved rollback version."""
import argparse
import datetime
import gzip
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path
from .admin import Admin, PROJECT
from .. import VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if not (args.build / 'index.html').exists(): raise SystemExit('Build index missing')
    admin = Admin()
    base = f'https://firebasehosting.googleapis.com/v1beta1/sites/{PROJECT}'
    previous = admin.request(base + '/releases?pageSize=5')
    args.evidence.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (args.evidence / f'hosting-before-{stamp}.json').write_text(json.dumps(previous, indent=2) + '\n')
    before = args.evidence / 'hosting-before.json'
    if not before.exists(): before.write_text(json.dumps(previous, indent=2) + '\n')
    config = json.loads(Path(__file__).with_name('firebase.json').read_text())['hosting']
    serving = {
        'rewrites': [{'glob': item['source'], 'path': item['destination']} for item in config['rewrites']],
        'headers': [{'glob': item['source'], 'headers': {h['key']: h['value'] for h in item['headers']}} for item in config['headers']],
    }
    version = admin.request(base + '/versions', 'POST', {'config': serving})
    name = version['name']
    packed, files = {}, {}
    for file in args.build.rglob('*'):
        if not file.is_file(): continue
        relative = file.relative_to(args.build)
        if any(part.startswith('.') for part in relative.parts): continue
        if file.suffix in ('.map', '.key', '.jks', '.sqlite3'): raise SystemExit('Private or debug file in public build')
        data = gzip.compress(file.read_bytes(), mtime=0)
        digest = hashlib.sha256(data).hexdigest()
        packed[digest] = data
        files['/' + relative.as_posix()] = digest
    populate = admin.request('https://firebasehosting.googleapis.com/v1beta1/' + name + ':populateFiles', 'POST', {'files': files})
    upload = populate['uploadUrl']
    if urllib.parse.urlparse(upload).hostname != 'upload-firebasehosting.googleapis.com':
        raise SystemExit('Unexpected Firebase upload origin')
    for digest in populate.get('uploadRequiredHashes', []):
        req = urllib.request.Request(upload + '/' + digest, data=packed[digest], method='POST',
            headers={'Authorization': 'Bearer ' + admin.token, 'Content-Type': 'application/octet-stream'})
        with urllib.request.urlopen(req, timeout=60) as response: response.read()
    admin.request('https://firebasehosting.googleapis.com/v1beta1/' + name + '?updateMask=status', 'PATCH', {'status':'FINALIZED'})
    release = admin.request(base + '/releases?versionName=' + urllib.parse.quote(name, safe=''), 'POST', {'message':f'SMART REHAB dashboard and user guide, hub {VERSION}'})
    (args.evidence / 'hosting-release.json').write_text(json.dumps(release, indent=2) + '\n')
    (args.evidence / f'hosting-release-{stamp}.json').write_text(json.dumps(release, indent=2) + '\n')
    print('Released https://smart-rehab-hub.web.app')


if __name__ == '__main__': main()
