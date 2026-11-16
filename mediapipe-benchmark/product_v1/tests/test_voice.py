import hashlib
import json
import subprocess
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from product_v1.voice import Voice
from product_v1.voice_pack import FORMAT, PIPER_VOICE, REQUIRED, number_vi, validate_pack


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        example = self.folder / 'sample.wav'
        with wave.open(str(example), 'wb') as wav:
            wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x01\x00' * 4410)
        data = example.read_bytes()
        files = {}
        for key in REQUIRED:
            (self.folder / (key + '.wav')).write_bytes(data)
            files[key] = {'sha256': hashlib.sha256(data).hexdigest()}
        self.manifest = dict(voice=PIPER_VOICE, provider='piper', language='vi-VN', format=FORMAT, files=files)
        self.save_manifest()

    def save_manifest(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_valid_pack_and_vietnamese_counts(self):
        self.assertEqual(set(validate_pack(self.folder)['files']), REQUIRED)
        for number, expected in {5:'năm', 15:'mười lăm', 21:'hai mươi mốt', 25:'hai mươi lăm',
                                 100:'một trăm', 101:'một trăm lẻ một', 115:'một trăm mười lăm',
                                 199:'một trăm chín mươi chín', 200:'hai trăm'}.items():
            self.assertEqual(number_vi(number), expected)
        for number in (0, -1, 201, True):
            with self.assertRaises(ValueError):
                number_vi(number)

    def test_missing_count_fails_closed(self):
        (self.folder / 'rep_200.wav').unlink()
        voice = Voice(self.folder)
        self.addCleanup(voice.close)
        self.assertFalse(voice.ready)

    def test_tampered_file_rejected(self):
        (self.folder / 'ready.wav').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            validate_pack(self.folder)

    def test_hash_matching_invalid_audio_rejected(self):
        data = b'not a wav file'
        (self.folder / 'ready.wav').write_bytes(data)
        self.manifest['files']['ready']['sha256'] = hashlib.sha256(data).hexdigest()
        self.save_manifest()
        voice = Voice(self.folder)
        self.addCleanup(voice.close)
        self.assertFalse(voice.ready)

    def test_partial_manifest_rejected(self):
        del self.manifest['files']['camera_lost']
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate_pack(self.folder)

    def test_unknown_voice_rejected(self):
        self.manifest['voice'] = 'unknown'
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            validate_pack(self.folder)

    def test_slow_playback_keeps_latest_rep_and_end_flushes(self):
        started, release = threading.Event(), threading.Event()
        calls = []
        def play(args, **kwargs):
            calls.append(Path(args[-1]).stem)
            started.set()
            release.wait(2)
        with patch('product_v1.voice.subprocess.run', side_effect=play):
            voice = Voice(self.folder)
            try:
                voice.say('prepare_squat')
                self.assertTrue(started.wait(2))
                for number in range(1, 202):
                    voice.count(number)
                with voice.condition:
                    self.assertEqual(list(voice.queue), [('rep_many', True)])
                voice.say('completed')
                with voice.condition:
                    self.assertEqual(list(voice.queue), [('completed', False)])
                release.set()
                deadline = time.monotonic() + 2
                while not voice.idle() and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertTrue(voice.idle())
                self.assertEqual(calls, ['prepare_squat', 'completed'])
            finally:
                release.set()
                voice.close()

    def test_player_failure_marks_audio_unavailable(self):
        with patch('product_v1.voice.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'aplay')):
            voice = Voice(self.folder)
            try:
                voice.say('ready')
                deadline = time.monotonic() + 2
                while voice.ready and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertFalse(voice.ready)
            finally:
                voice.close()
