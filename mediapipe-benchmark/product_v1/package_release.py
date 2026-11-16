"""Build a versioned, credential-free hub installer from the verified Pi assets."""
import argparse
import copy
import hashlib
import io
import json
import tarfile
from pathlib import Path
from . import VERSION
from .voice_pack import REQUIRED, validate_pack


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--update-only', action='store_true')
    args = parser.parse_args()
    audio_manifest = validate_pack(args.audio)
    audio_names = sorted({key + '.wav' for key in REQUIRED} | {'manifest.json', 'ATTRIBUTION.md'})
    audio_files = [args.audio / name for name in audio_names]
    if not all(p.is_file() for p in audio_files):
        raise SystemExit('Complete local audio and attribution are required')
    root = Path(__file__).resolve().parent.parent
    args.output.mkdir(parents=True, exist_ok=True)
    files = []
    for folder in ('product_v1', 'pose_algorithm'):
        for p in sorted((root / folder).rglob('*')):
            if not p.is_file() or p.suffix == '.pyc' or any(part in ('__pycache__', 'cloud') for part in p.relative_to(root).parts):
                continue
            if p.name.startswith('e2e_') or p.name in ('make_voice_pack.py', 'make_piper_pack.py', 'package_release.py'):
                continue
            files.append(p)
    files += [root / 'integration_v1' / name for name in
              ('__init__.py', 'transport.py', 'storage.py', 'persistent_safety.py', 'ram_safety.py')]
    manifest = {'version': VERSION, 'platform': 'Raspberry Pi 4 ARM64, Debian 13, labwc',
                'assets_sha256': hashlib.sha256(args.assets.read_bytes()).hexdigest(),
                'source_files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                'voice': audio_manifest['voice'],
                'audio_files': {'product_v1/audio/' + p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in audio_files}}
    for full in ((False,) if args.update_only else (False, True)):
        path = args.output / f'smart-rehab-hub-{VERSION}{"-full" if full else "-update"}.tar.gz'
        with tarfile.open(path, 'w:gz', compresslevel=3) as output:
            for p in files:
                output.add(p, arcname=p.relative_to(root).as_posix(), recursive=False)
            for p in audio_files:
                output.add(p, arcname='product_v1/audio/' + p.name, recursive=False)
            encoded = (json.dumps(manifest, indent=2) + '\n').encode()
            info = tarfile.TarInfo('release-manifest.json'); info.size = len(encoded); info.mode = 0o644
            output.addfile(info, io.BytesIO(encoded))
            if full:
                with tarfile.open(args.assets, 'r:gz') as assets:
                    for item in assets:
                        if item.name.startswith('/') or '..' in Path(item.name).parts:
                            raise ValueError('unsafe_asset_path')
                        target = copy.copy(item)
                        target.name = 'device-assets/' + item.name
                        if item.islnk(): target.linkname = 'device-assets/' + item.linkname
                        output.addfile(target, assets.extractfile(item) if item.isfile() else None)
        print(f'Created {path.name}: {path.stat().st_size} bytes', flush=True)
    (args.output / 'hub-release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__': main()
