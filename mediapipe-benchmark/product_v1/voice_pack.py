"""Shared local-audio contract. No synthesis engine or network access on the hub."""
import hashlib
import json
import wave
from pathlib import Path

FORMAT = 'wav_pcm_s16le_22050_mono'
PIPER_VOICE = 'vi_VN-vais1000-medium'
PROMPTS = {
    'prepare_squat': 'Mời bạn đứng nghiêng trước máy quay, để thấy rõ hông, đầu gối và bàn chân.',
    'prepare_biceps_curl': 'Mời bạn đứng nghiêng trước máy quay, thả tay xuống để thấy rõ vai, khuỷu tay và cổ tay.',
    'ready': 'Đã sẵn sàng. Bạn có thể bắt đầu tập.',
    'lost': 'Máy chưa thấy rõ khớp. Bạn chỉnh lại vị trí một chút nhé.',
    'recovered': 'Đã thấy rõ. Mời bạn tiếp tục.',
    'completed': 'Bạn đã hoàn thành buổi tập. Mời bạn nghỉ ngơi.',
    'stopped': 'Buổi tập đã dừng. Kết quả của bạn đã được lưu.',
    'network_lost': 'Hub bị mất mạng. Buổi tập đã dừng và kết quả được lưu lại.',
    'camera_lost': 'Máy quay bị ngắt kết nối. Buổi tập đã dừng.',
    'interrupted': 'Buổi tập đã dừng. Bạn kiểm tra thông báo trên điện thoại nhé.',
    'rep_many': 'Tốt lắm. Mời bạn tiếp tục.',
    'sample': 'Xin chào, mình sẽ đồng hành cùng bạn trong buổi tập hôm nay. Bạn nghe có rõ không?',
}
from .catalog import EXERCISE_CATALOG
PROMPTS.update({e['voice_key']: e['camera_text'] + ' ' + e['steps'][0] for e in EXERCISE_CATALOG.values()})
PROMPTS.update({
    'hold_ready': 'Giữ tư thế này. Chờ đếm ngược trên màn hình rồi bắt đầu tập nhé.',
    'side_both': 'Buổi này tập cả hai bên cùng lúc. Cùng nâng lên, cùng trở về tư thế đầu để tính một lần.',
    'side_left': 'Buổi này tập bên trái của bạn.',
    'side_right': 'Buổi này tập bên phải của bạn.',
    'set_start': 'Đã sẵn sàng. Mời bạn bắt đầu hiệp tập.',
    'set_rest': 'Đã đủ số lần trong hiệp. Mời bạn nghỉ.',
    'set_prepare': 'Hết thời gian nghỉ. Mời bạn về tư thế ban đầu cho hiệp tiếp theo.',
    'goal_complete': 'Bạn đã hoàn thành đủ các hiệp. Mời bạn nghỉ ngơi.',
})
PROMPTS.update({'prepare_both_' + e['id']: e['both_camera_text'] + ' Về tư thế đầu ở cả hai bên.' for e in EXERCISE_CATALOG.values() if e.get('bilateral')})
REQUIRED = set(PROMPTS) | {f'rep_{i}' for i in range(1, 201)}


def number_vi(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 200:
        raise ValueError('voice_number_out_of_range')
    digits = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']
    if n < 10:
        return digits[n]
    if n == 200:
        return 'hai trăm'
    if n >= 100:
        return 'một trăm' + ('' if n == 100 else ' lẻ ' + digits[n % 100] if n % 100 < 10 else ' ' + number_vi(n % 100))
    tens, unit = divmod(n, 10)
    head = 'mười' if tens == 1 else digits[tens] + ' mươi'
    tail = '' if unit == 0 else ' lăm' if unit == 5 else ' mốt' if unit == 1 and tens > 1 else ' ' + digits[unit]
    return head + tail


def wav_duration(path):
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 22050, 'NONE'):
            raise ValueError('invalid_voice_format')
        frames = wav.getnframes()
        if not .12 <= frames / 22050 <= 18:
            raise ValueError('invalid_voice_duration')
        if len(wav.readframes(frames)) != frames * 2:
            raise ValueError('truncated_voice_audio')
        return frames / 22050


def validate_pack(directory):
    """Return a validated manifest, or fail before a session can open the camera."""
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('voice') not in ('lannhi', PIPER_VOICE) or manifest.get('format') != FORMAT:
        raise ValueError('unsupported_voice_pack')
    if manifest['voice'] == PIPER_VOICE and (manifest.get('provider') != 'piper' or manifest.get('language') != 'vi-VN'):
        raise ValueError('invalid_voice_metadata')
    files = manifest['files']
    if not isinstance(files, dict) or not REQUIRED <= files.keys():
        raise ValueError('incomplete_voice_pack')
    for name in REQUIRED:
        path = directory / (name + '.wav')
        if hashlib.sha256(path.read_bytes()).hexdigest() != files[name]['sha256']:
            raise ValueError('voice_checksum_mismatch')
        wav_duration(path)
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    pack = validate_pack(args.directory)
    print(f'Validated {len(REQUIRED)} local clips: {pack["voice"]}')
