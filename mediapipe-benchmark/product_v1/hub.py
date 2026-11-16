"""Boot service for a paired hub. No shell commands are accepted from clients."""
import argparse
import json
import logging
import os
import signal
import threading
import time
import uuid
from pathlib import Path
from .catalog import CAPABILITIES, EXERCISE_CATALOG
from . import VERSION
from .cloud_client import Cloud
from .display import Display
from .engine import run_session
from .protocol import ROOT, safe_id, validate_command, command_goal
from .movement import algorithm_version
from .session import Session, epoch_ms, recover_interrupted
from .state import Store
from .voice import Voice

LOG = logging.getLogger('smart-rehab')


class Hub:
    def __init__(self, config, store, cloud, display, voice, runner=run_session):
        self.config, self.store, self.cloud, self.display, self.voice, self.runner = config, store, cloud, display, voice, runner
        self.id = safe_id(config['hub_id'])
        self.lock, self.stop, self.session_stop = threading.RLock(), threading.Event(), threading.Event()
        self.owner = store.get('owner_uid')
        self.session, self.thread, self.latest = None, None, None
        self.state, self.reason, self.safety_fault = 'idle', None, None
        self.provisioning = False
        self.meta_delivered = set()
        self.last_latest = 0.0
        recover_interrupted(store)
        self.display.bind_health(self.tv_health)

    def tv_health(self):
        with self.lock:
            return dict(online=time.monotonic()-self.cloud.last_success < 5,
                        paired=bool(self.owner), audio_ready=self.voice.ready,
                        storage_fault=bool(self.safety_fault))

    def status(self):
        with self.lock:
            online = time.monotonic() - self.cloud.last_success < 5
            value = dict(state=self.state, updated_at=epoch_ms(), version=VERSION,
                         audio_ready=self.voice.ready, display_ready=self.display.ready,
                         ready=bool(self.owner and online and self.voice.ready and self.display.ready and not self.safety_fault))
            value['capabilities'] = CAPABILITIES
            if self.session:
                value.update(session_id=self.session.sid, exercise=self.session.meta['exercise'])
                value.update(self.session.live())
            if self.reason or self.safety_fault:
                value['reason'] = self.safety_fault or self.reason
            return value

    def command(self, command_id, command):
        try:
            safe_id(command_id)
        except ValueError:
            return
        with self.lock:
            old = self.store.acknowledgement(command_id)
            if old:
                self.store.enqueue(f'{ROOT}/acks/{self.id}/{command_id}', old)
                return
            ack = dict(status='rejected', at=epoch_ms())
            meta = None
            try:
                validate_command(command, self.owner, epoch_ms())
                if command['action'] == 'start':
                    if self.provisioning:
                        raise ValueError('provisioning_active')
                    if self.session is not None or (self.thread and self.thread.is_alive()):
                        raise ValueError('session_already_active')
                    if self.safety_fault:
                        raise ValueError('storage_unavailable')
                    if time.monotonic() - self.cloud.last_success > 5:
                        raise ValueError('hub_offline')
                    if not self.display.ready:
                        raise ValueError('display_unavailable')
                    if not self.voice.ready:
                        raise ValueError('audio_unavailable')
                    sid = 's_' + uuid.uuid4().hex
                    goal = command_goal(command)
                    meta = dict(session_id=sid, hub_id=self.id, patient_uid=self.owner,
                                exercise=command['exercise'], duration_s=goal.get('duration_s', 1800),
                                protocol_version=command.get('protocol_version', 1), goal=goal,
                                requested_side=command.get('requested_side', 'auto'),
                                catalog_version=CAPABILITIES['catalog_version'],
                                preset_version=EXERCISE_CATALOG[command['exercise']]['algorithm_version'],
                                schema_version=2, algorithm_version=algorithm_version(command['exercise'], command.get('requested_side', 'auto')), created_at=epoch_ms(),
                                source='camera', form_status='not_evaluated')
                    ack.update(status='accepted', session_id=sid)
                else:
                    if self.session is None or self.session.sid != command['session_id']:
                        raise ValueError('session_not_active')
                    ack.update(status='accepted', session_id=self.session.sid)
            except ValueError as error:
                ack['reason'] = str(error)
            self.store.accept(command_id, ack, meta)
            if meta:
                self.session = Session(self.store, meta)
                self.session_stop = threading.Event()
                self.state, self.reason = 'preparing', None
                self.display.begin(meta)
            self.store.enqueue(f'{ROOT}/acks/{self.id}/{command_id}', ack)
            if meta:
                self.thread = threading.Thread(target=self._exercise, name='exercise', daemon=True)
                self.thread.start()
            elif ack['status'] == 'accepted':
                self.state = 'stopping'
                self.display.stopping()
                self.session_stop.set()

    def _exercise(self):
        reason = 'engine_error'
        try:
            reason = self.runner(self.session, self.config, self.display, self.voice,
                                 self.session_stop, self.cloud, self.sample)
        except Exception as error:
            # Exception text from network/model libraries may contain sensitive paths or URLs.
            LOG.error('Session failed: %s', type(error).__name__)
            if isinstance(error, RuntimeError) and str(error) in ('camera_unavailable', 'camera_disconnected', 'camera_shutdown_timeout'):
                reason = str(error)
        finally:
            with self.lock:
                if self.stop.is_set():
                    reason = 'hub_shutdown'
                elif self.safety_fault:
                    reason = 'storage_unavailable'
                self.latest = None
                self.display.blank()
                summary = self.session.finish(reason)
                self.display.finish(summary)
                self.session = None
                self.state, self.reason = 'idle', reason
            prompt = {'duration_complete': 'completed', 'goal_complete': 'goal_complete', 'patient_stop': 'stopped',
                      'internet_lost': 'network_lost', 'camera_disconnected': 'camera_lost'}.get(reason, 'interrupted')
            self.voice.say(prompt)
            # A blocked USB driver must not leave an old camera thread sharing a new session.
            if reason == 'camera_shutdown_timeout':
                os._exit(75)  # systemd restarts; durable summary was committed above.

    def sample(self, value, phase):
        with self.lock:
            self.latest = {k: v for k, v in value.items() if k != 'rep_event'}
            if self.state != 'stopping':
                self.state = phase

    def _cloud_loop(self):
        heartbeat, owner_check = 0, 0
        while not self.stop.is_set():
            try:
                now = time.monotonic()
                if now - owner_check >= 10:
                    registry = self.cloud.get(f'{ROOT}/hubs/{self.id}') or {}
                    self.owner = registry.get('owner_uid')
                    self.store.set('owner_uid', self.owner)
                    owner_check = now
                if now - heartbeat >= 2:
                    self.cloud.put(f'{ROOT}/hubState/{self.id}', self.status())
                    heartbeat = now
                # Bounded batch prevents historical retries from starving the heartbeat.
                for _ in range(4):
                    pending = self.store.pending()
                    if not pending:
                        break
                    self.cloud.put(pending[1], pending[2])
                    if pending[1].endswith('/meta'):
                        self.meta_delivered.add(pending[2]['session_id'])
                    self.store.sent(pending)
                with self.lock:
                    current = dict(self.latest) if self.latest and self.session else None
                    if current and current['session_id'] in self.meta_delivered and now - self.last_latest >= .5:
                        self.latest = None
                    else:
                        current = None
                if current and 0 <= epoch_ms() - current['frame_received_epoch_ms'] < 2000:
                    current['timestamp'] = epoch_ms()
                    self.last_latest = time.monotonic()
                    with self.lock:
                        still_active = self.session and self.session.sid == current['session_id']
                    if still_active:
                        self.cloud.put(f'{ROOT}/sessions/{current["session_id"]}/latest', current)
            except (OSError, RuntimeError, ValueError):
                self.stop.wait(.5)
            self.stop.wait(.1)

    def start(self):
        threading.Thread(target=self._cloud_loop, name='cloud-outbox', daemon=True).start()
        threading.Thread(target=self.cloud.commands, args=(self.id, self.stop, self.command), name='commands', daemon=True).start()

    def close(self):
        self.stop.set(); self.session_stop.set()
        if self.thread:
            self.thread.join(15)
        self.voice.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(Path.home() / '.config/smart-rehab/product.json'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    path = Path(args.config)
    if path.stat().st_mode & 0o077:
        raise SystemExit('Device configuration must have mode 0600')
    config = json.loads(path.read_text())
    directory = Path(config['state_dir']); directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Store(directory / 'hub.sqlite3')
    cloud, display = Cloud(config), Display()
    # Bundled audio follows the release symlink, including during rollback.
    bundled_audio = Path(__file__).resolve().parent / 'audio'
    audio_directory = bundled_audio if bundled_audio.is_dir() else Path(config['audio_dir'])
    voice = Voice(audio_directory, config.get('audio_device', 'plughw:CARD=Headphones,DEV=0'))
    hub = Hub(config, store, cloud, display, voice)
    from integration_v1.persistent_safety import PersistentGuard
    from .ble import start_ble
    guard = PersistentGuard(directory)
    def safety():
        while not hub.stop.wait(2):
            fault = guard.poll()['safety_fault']
            if fault:
                hub.safety_fault = fault
                hub.session_stop.set()
    threading.Thread(target=safety, name='storage-guard', daemon=True).start()
    start_ble(hub, config, path)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: (hub.stop.set(), hub.session_stop.set()))
    hub.start()
    try:
        display.run(hub.stop)
    finally:
        hub.close()


if __name__ == '__main__':
    main()
