"""Validated local audio only. One player, bounded queue, newest rep wins."""
import subprocess
import threading
import wave
from collections import deque
from pathlib import Path

from .voice_pack import PROMPTS, validate_pack


class TrackingReminder:
    """One reminder after 3s of loss; stable tracking for 2s rearms it."""
    def __init__(self):
        self.lost_since = self.seen_since = None
        self.notified = False

    def update(self, tracking, working, now):
        if not working:
            self.lost_since = self.seen_since = None
            self.notified = False
        elif tracking:
            self.lost_since = None
            if self.seen_since is None:
                self.seen_since = now
            if now-self.seen_since >= 2:
                self.notified = False
        else:
            self.seen_since = None
            if self.lost_since is None:
                self.lost_since = now
            if not self.notified and now-self.lost_since >= 3:
                self.notified = True
                return True
        return False


class Voice:
    def __init__(self, directory, device='plughw:CARD=Headphones,DEV=0'):
        self.directory, self.device = Path(directory), device
        self.ready = False
        self.queue, self.condition, self.closed = deque(), threading.Condition(), False
        self.playing = False
        try:
            validate_pack(self.directory)
            self.ready = True
        except (OSError, ValueError, KeyError, TypeError, AttributeError, EOFError, wave.Error):
            self.ready = False
        self.thread = threading.Thread(target=self._work, name='local-voice', daemon=True)
        self.thread.start()

    def say(self, key, *, rep=False):
        if not self.ready:
            return
        with self.condition:
            if rep:
                self.queue = deque((k, r) for k, r in self.queue if not r and k not in ('lost', 'recovered'))
            elif key in ('completed', 'stopped', 'network_lost', 'camera_lost', 'interrupted',
                         'goal_complete', 'set_rest', 'set_prepare', 'set_start', 'ready', 'hold_ready'):
                self.queue.clear()
            if len(self.queue) < 4:
                self.queue.append((key, rep))
            self.condition.notify()

    def count(self, number):
        if number > 0:
            self.say(f'rep_{number}' if number <= 200 else 'rep_many', rep=True)

    def idle(self):
        with self.condition:
            return not self.playing and not self.queue

    def _work(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.queue)
                if self.closed:
                    return
                key, _ = self.queue.popleft()
                self.playing = True
            try:
                subprocess.run(['aplay', '-q', '-D', self.device, str(self.directory / (key + '.wav'))],
                               check=True, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                self.ready = False
            finally:
                with self.condition:
                    self.playing = False

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify()
        self.thread.join(21)
