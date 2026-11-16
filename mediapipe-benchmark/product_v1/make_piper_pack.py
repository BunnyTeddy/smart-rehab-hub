"""Build WAV assets once on the development computer; the Pi needs only aplay."""
import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import tempfile
import wave
from pathlib import Path
from .voice_pack import FORMAT, PIPER_VOICE, PROMPTS, number_vi, validate_pack, wav_duration

MODEL_SOURCE = 'https://huggingface.co/rhasspy/piper-voices/tree/main/vi/vi_VN/vais1000/medium'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sample-only', action='store_true')
    args = parser.parse_args()
    if args.model.name != PIPER_VOICE + '.onnx':
        raise SystemExit('Use the reviewed vi_VN-vais1000-medium voice')
    from piper import PiperVoice, SynthesisConfig
    model_config = Path(str(args.model) + '.json')
    config = json.loads(model_config.read_text())
    if config['audio']['sample_rate'] != 22050 or config['espeak']['voice'] != 'vi':
        raise SystemExit('Unexpected Piper voice configuration')
    args.output.mkdir(parents=True, exist_ok=True)
    fingerprint = {'model_sha256': sha(args.model), 'config_sha256': sha(model_config),
                   'piper_version': importlib.metadata.version('piper-tts'),
                   'length_scale': 1.08, 'noise_scale': .5, 'noise_w_scale': .65,
                   'normalization': 'loudnorm=I=-18:TP=-2:LRA=7'}
    path = args.output / 'manifest.json'
    manifest = {'schema_version': 1, 'provider': 'piper', 'voice': PIPER_VOICE,
                'language': 'vi-VN', 'format': FORMAT, 'source': MODEL_SOURCE,
                'build': fingerprint, 'human_listening_verified': False, 'files': {}}
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest.get('build') != fingerprint or manifest.get('voice') != PIPER_VOICE:
            raise SystemExit('Choose a new output directory for a different voice build')
    texts = {'sample': PROMPTS['sample']} if args.sample_only else {
        **PROMPTS, **{f'rep_{i}': number_vi(i) + '.' for i in range(1, 201)}}
    voice = PiperVoice.load(args.model, use_cuda=False)
    syn = SynthesisConfig(length_scale=1.08, noise_scale=.5, noise_w_scale=.65)
    print(f'Piper local generation: {len(texts)} clips; no API key or cloud synthesis.', flush=True)
    with tempfile.TemporaryDirectory(prefix='rehab-piper-') as temp:
        for key, text in texts.items():
            destination = args.output / (key + '.wav')
            old = manifest['files'].get(key)
            if old and old.get('text') == text and destination.exists() and sha(destination) == old['sha256']:
                wav_duration(destination)
                continue
            raw, normalized = Path(temp) / 'raw.wav', Path(temp) / 'normalized.wav'
            with wave.open(str(raw), 'wb') as output:
                voice.synthesize_wav(text, output, syn_config=syn)
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-i', str(raw),
                            '-af', fingerprint['normalization'], '-ar', '22050', '-ac', '1',
                            '-c:a', 'pcm_s16le', str(normalized)], check=True)
            duration = wav_duration(normalized)
            destination.write_bytes(normalized.read_bytes())
            manifest['files'][key] = {'text': text, 'sha256': sha(destination), 'duration_s': round(duration, 4)}
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
            temporary.replace(path)
            print(f'{key}: {duration:.2f}s', flush=True)
    (args.output / 'ATTRIBUTION.md').write_text(
        '# SMART REHAB — bộ giọng tiếng Việt\n\n'
        'Được tổng hợp cục bộ bằng Piper của Open Home Foundation, giọng vi_VN-vais1000-medium.\n'
        'Model do Rhasspy/Michael Hansen phân phối, fine-tune từ giọng lessac.\n'
        'Nguồn model và model card: ' + MODEL_SOURCE + '\n\n'
        'Dữ liệu gốc: VAIS-1000 Vietnamese Speech Synthesis Corpus; model card ghi giấy phép '
        'Creative Commons Attribution 4.0: https://creativecommons.org/licenses/by/4.0/\n'
        'Piper: https://github.com/OHF-Voice/piper1-gpl (GPL-3.0); chỉ dùng trên máy tạo âm thanh, '
        'không đóng gói engine hoặc model TTS vào hub.\n'
        'Nội dung do SMART REHAB biên soạn; âm thanh được chuẩn hóa âm lượng và chuyển sang PCM mono 22.05 kHz.\n'
        'Chưa xác nhận giọng miền Nam hoặc chất lượng trên loa hub; không giả định tương đương FPT lannhi.\n')
    if not args.sample_only:
        validate_pack(args.output)
    print('Generation validated. Human listening on the hub speaker remains pending.', flush=True)


if __name__ == '__main__':
    main()
