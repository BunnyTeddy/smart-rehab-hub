"""One-time FPT lannhi synthesis. API key stays only on the build computer."""
import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from .voice_pack import PROMPTS, number_vi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key-file', type=Path, default=Path.home() / '.config/smart-rehab/fpt_tts.key')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sample-only', action='store_true')
    args = parser.parse_args()
    if args.key_file.stat().st_mode & 0o077:
        raise SystemExit('FPT key file must have mode 0600')
    api_key = args.key_file.read_text().strip()
    phrases = {'sample': PROMPTS['sample']} if args.sample_only else {**PROMPTS, **{f'rep_{i}': number_vi(i) + '.' for i in range(1, 201)}}
    characters = sum(len(v) for v in phrases.values())
    if characters > 100000:
        raise SystemExit('This pack exceeds the declared monthly free allowance')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'voice': 'lannhi', 'format': 'wav_pcm_s16le_22050_mono', 'files': {}}
    print(f'Pack: {len(phrases)} clips, {characters} characters. Existing valid clips are reused.', flush=True)
    for name, text in phrases.items():
        output = args.output / (name + '.wav')
        old = manifest['files'].get(name)
        if old and old.get('text') == text and output.exists() and old['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest():
            continue
        request = urllib.request.Request('https://api.fpt.ai/hmi/tts/v5', data=text.encode(), method='POST',
            headers={'api_key': api_key, 'voice': 'lannhi', 'speed': '0', 'format': 'mp3'})
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        if result.get('error') != 0:
            raise SystemExit('FPT rejected synthesis; check account quota or key privately. No paid fallback.')
        url = result['async']
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ''
        fpt_origin = host.endswith(('.fpt.ai', '.fptai.com'))
        documented_s3 = host == 's3-ap-southeast-1.amazonaws.com' and parsed.path.startswith('/text2speech-')
        if parsed.scheme != 'https' or not (fpt_origin or documented_s3):
            raise SystemExit('Unexpected audio download origin; inspect FPT response privately')
        encoded = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(url, timeout=15) as response: encoded = response.read()
                if encoded: break
            except urllib.error.HTTPError as error:
                if error.code not in (404, 403): raise
            time.sleep(2)
        if not encoded: raise SystemExit('FPT audio did not become available; rerun to resume')
        # The API key is not inherited by this child, stored, logged or packaged.
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', 'pipe:0', '-ar', '22050', '-ac', '1',
                        '-af', 'loudnorm=I=-18:TP=-2:LRA=7', '-c:a', 'pcm_s16le', '-y', str(output)], input=encoded, check=True)
        manifest['files'][name] = {'text': text, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        print('Generated ' + name, flush=True)
        time.sleep(.4)
    print('Generation complete. Human listening approval on the actual hub speaker is still required.')


if __name__ == '__main__': main()
