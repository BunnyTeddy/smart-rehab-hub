"""Device-owned clock and set lifecycle; the phone only observes acknowledged state."""
import math
import time
from .protocol import ROOT


def epoch_ms():
    return time.time_ns() // 1_000_000


class Session:
    def __init__(self, store, meta, *, monotonic=time.monotonic, wall=epoch_ms, recover=False):
        self.store, self.meta, self.clock, self.wall = store, meta, monotonic, wall
        self.sid = meta['session_id']
        self.prefix = f'{ROOT}/sessions/{self.sid}'
        self.goal = meta.get('goal') or {'mode': 'time', 'duration_s': meta['duration_s']}
        self.limit = self.goal['duration_s'] if self.goal['mode'] == 'time' else 1800
        self.created = self.clock()
        self.started = None
        self.last_tick = self.created
        self.align_since = self.created
        self.rest_until = None
        self.last_sample = None
        self.was_tracking = False
        self.last_timestamp = None
        self.last_point = -1
        self.last_checkpoint = -1
        self.finished = False
        self.recovering = recover
        self.progress = dict(started_at=None, elapsed_s=0.0, tracking_s=0.0, reps=0,
                             measured_samples=0, max_temperature_c=None, throttled='unknown',
                             workload_phase='aligning', set_number=1, rep_in_set=0,
                             completed_sets=0, set_results={}, active_s=0.0, rest_s=0.0, aligning_s=0.0)
        self.latencies = []
        if recover:
            self.progress.update(store.get('progress', {}))
        self.store.enqueue(self.prefix + '/meta', meta)
        if not recover:
            self.checkpoint()
            self.index('preparing')

    @property
    def phase(self):
        # Legacy Android must still see an active, stoppable session during rest.
        return 'running' if self.started is not None else 'aligning'

    @property
    def workload_phase(self):
        return self.progress['workload_phase']

    @property
    def completion_reason(self):
        return self.progress.get('completion_reason')

    def checkpoint(self):
        self.store.set('progress', self.progress)
        self.last_checkpoint = self.clock()

    def index_value(self, status, ended_at=None):
        value = {k: self.meta[k] for k in ('session_id', 'exercise', 'created_at')}
        value.update(status=status, reps=self.progress['reps'], goal=self.goal,
                     requested_side=self.meta.get('requested_side', 'auto'),
                     algorithm_version=self.meta['algorithm_version'],
                     completed_sets=self.progress['completed_sets'],
                     elapsed_s=round(self.progress['elapsed_s'], 3),
                     active_s=round(self.progress['active_s'], 3),
                     tracking_s=round(self.progress['tracking_s'], 3))
        if ended_at is not None:
            value['ended_at'] = ended_at
        return value

    def index(self, status, ended_at=None):
        self.store.enqueue(f'{ROOT}/patientSessions/{self.meta["patient_uid"]}/{self.sid}', self.index_value(status, ended_at), replace=True)

    def tick(self):
        """Account wall time independently of successful pose inference."""
        now = self.clock()
        if self.finished or self.completion_reason:
            return self.completion_reason
        end = min(now, self.started + self.limit) if self.started is not None else now
        if self.started is not None:
            cursor = max(self.last_tick, self.started)
            if self.workload_phase == 'resting':
                rest_end = min(end, self.rest_until)
                self.progress['rest_s'] += max(0, rest_end - cursor)
                cursor = max(cursor, rest_end)
            key = {'working': 'active_s', 'aligning': 'aligning_s', 'resting': 'aligning_s'}[self.workload_phase]
            delta = max(0, end - cursor)
            self.progress[key] += delta
            if key == 'active_s' and self.goal['mode'] == 'sets':
                current = self.progress['set_results'].get(f'set{self.progress["set_number"]:03d}')
                if current:
                    current['active_s'] += delta
            self.progress['elapsed_s'] = max(0, end - self.started)
        self.last_tick = end
        if self.started is not None and now >= self.started + self.limit:
            self.progress['completion_reason'] = 'duration_complete' if self.goal['mode'] == 'time' else 'session_limit'
            self.progress['workload_phase'] = 'complete'
            self.checkpoint()
        elif self.workload_phase == 'resting' and now >= self.rest_until:
            self.progress['workload_phase'] = 'aligning'
            self.progress['set_number'] += 1
            self.progress['rep_in_set'] = 0
            self.align_since = self.rest_until
            self.checkpoint()
        elif self.workload_phase == 'aligning' and now - self.align_since >= 120:
            self.progress['completion_reason'] = 'preparation_timeout'
            self.progress['workload_phase'] = 'complete'
            self.checkpoint()
        return self.completion_reason

    def live(self):
        now = self.clock()
        return dict(workload_phase=self.workload_phase, goal=self.goal,
                    requested_side=self.meta.get('requested_side', 'auto'),
                    set_number=self.progress['set_number'], rep_in_set=self.progress['rep_in_set'],
                    completed_sets=self.progress['completed_sets'],
                    remaining_s=max(0, self.limit-self.progress['elapsed_s']),
                    rest_remaining_s=max(0, (self.rest_until or now)-now) if self.workload_phase == 'resting' else 0,
                    elapsed_s=self.progress['elapsed_s'], active_s=self.progress['active_s'])

    def sample(self, result, *, algorithm_ms=0.0, allow_start=True):
        if self.finished:
            raise ValueError('session_already_finished')
        now = self.clock()
        self.tick()
        timestamp = result['sample_timestamp_ms']
        if self.last_timestamp is not None and timestamp <= self.last_timestamp:
            result['rep_event'] = None
            result['reps'] = self.progress['reps']
            return bool(self.completion_reason)
        self.last_timestamp = timestamp
        was_working = self.workload_phase == 'working'
        if self.workload_phase == 'aligning' and allow_start and result['phase'] == 'READY' and result['tracking_status'] == 'tracking':
            if self.started is None:
                self.started = now
                self.last_tick = now
                self.progress['started_at'] = self.wall()
            self.progress['workload_phase'] = 'working'
            self.was_tracking = False
            if self.goal['mode'] == 'sets':
                self.progress['set_results'][f'set{self.progress["set_number"]:03d}'] = dict(
                    set_number=self.progress['set_number'], reps=0, completed=False, active_s=0.0, started_at=self.wall())
            self.checkpoint()
            self.index('running')
        working = self.workload_phase == 'working'
        if self.started is not None and not self.completion_reason:
            self.progress['measured_samples'] += 1
            self.latencies.append(algorithm_ms)
        if working and was_working and self.last_sample is not None and self.was_tracking and result['tracking_status'] == 'tracking':
            gap = now-self.last_sample
            if 0 < gap <= .35:
                self.progress['tracking_s'] += gap
        self.last_sample = now
        self.was_tracking = working and result['tracking_status'] == 'tracking'
        event = result.get('rep_event') if working and was_working else None
        result['rep_event'] = None
        if event:
            self.progress['reps'] += 1
            self.progress['rep_in_set'] += 1
            n = self.progress['reps']
            event = {**event, 'id': f'{self.sid}:rep:{n}', 'rep': n,
                     'set_number': self.progress['set_number'], 'rep_in_set': self.progress['rep_in_set']}
            if self.goal['mode'] == 'sets':
                current = self.progress['set_results'][f'set{self.progress["set_number"]:03d}']
                current['reps'] = self.progress['rep_in_set']
                if self.progress['rep_in_set'] == self.goal['reps_per_set']:
                    current.update(completed=True, ended_at=self.wall())
                    self.progress['completed_sets'] += 1
                    if self.progress['completed_sets'] == self.goal['sets']:
                        self.progress['workload_phase'] = 'complete'
                        self.progress['completion_reason'] = 'goal_complete'
                    else:
                        self.progress['workload_phase'] = 'resting'
                        self.rest_until = now + self.goal['rest_s']
            # Last rep + completed set + next phase are ONE commit, including the terminal marker.
            self.store.rep_checkpoint(self.prefix + f'/events/rep{n:06d}', event, self.progress)
            self.last_checkpoint = now
            result['rep_event'] = event
            self.index(self.phase)
        result['reps'] = self.progress['reps']
        result.update(self.live())
        second = int(timestamp // 1000)
        if second > self.last_point:
            point = dict(t_ms=timestamp, angle=result['angle'], tracking_status=result['tracking_status'],
                         workload_phase=self.workload_phase, set_number=self.progress['set_number'])
            for key in ('reason', 'phase', 'angle_left', 'angle_right'):
                if key in result:
                    point[key] = result[key]
            self.store.enqueue(self.prefix + f'/points/p{second:06d}', point)
            self.last_point = second
        if not event and now - self.last_checkpoint >= 1:
            self.checkpoint()
        return bool(self.completion_reason)

    def sensors(self, temperature, throttled):
        if temperature is not None and math.isfinite(temperature):
            self.progress['max_temperature_c'] = max(temperature, self.progress['max_temperature_c'] or 0)
        if throttled and (self.progress['throttled'] in ('unknown', 'throttled=0x0') or throttled != 'throttled=0x0'):
            self.progress['throttled'] = throttled

    def finish(self, reason):
        if self.finished:
            return self.store.get('last_summary')
        if not self.recovering:
            self.tick()
        # A crash after the final rep must preserve the already committed completion.
        reason = self.completion_reason or reason
        ended = self.wall()
        status = 'completed' if reason in ('duration_complete', 'goal_complete') else 'stopped' if reason == 'patient_stop' else 'interrupted'
        summary = {k: self.meta[k] for k in ('session_id', 'hub_id', 'patient_uid', 'exercise')}
        public = {k: v for k, v in self.progress.items() if k not in ('completion_reason', 'workload_phase', 'set_number', 'rep_in_set')}
        summary.update(public, goal=self.goal, requested_side=self.meta.get('requested_side', 'auto'),
                       algorithm_version=self.meta['algorithm_version'], status=status, error=reason, ended_at=ended, form_status='not_evaluated')
        duration = self.progress['elapsed_s']
        summary['inference_fps'] = self.progress['measured_samples'] / duration if duration > 0 else 0.0
        ordered = sorted(self.latencies)
        summary['algorithm_p95_ms'] = ordered[min(len(ordered)-1, int(len(ordered)*.95))] if ordered else 0.0
        self.store.complete_session(self.prefix+'/summary', summary,
                                    f'{ROOT}/patientSessions/{self.meta["patient_uid"]}/{self.sid}',
                                    self.index_value(status, ended))
        self.finished = True
        return summary


def recover_interrupted(store):
    active = store.get('active')
    if active:
        return Session(store, active, recover=True).finish('hub_restarted')
    return None
