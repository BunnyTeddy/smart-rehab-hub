"""MediaPipe Lite + unchanged v2 algorithm, without a video recorder."""
import threading
import time
from .movement import create_algorithm
from .tv_state import ReadyCountdown
from .diagnostics import DetectionDiagnostics
from .voice import TrackingReminder


class Camera:
    def __init__(self, device, cv2):
        self.cv2, self.device = cv2, device
        self.condition, self.stop = threading.Condition(), threading.Event()
        self.latest, self.error, self.number = None, None, 0
        self.thread = threading.Thread(target=self._capture, name='camera', daemon=True)
        self.thread.start()

    def _capture(self):
        cv2 = self.cv2
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        try:
            if not cap.isOpened():
                raise RuntimeError('camera_unavailable')
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            while not self.stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError('camera_disconnected')
                with self.condition:
                    self.number += 1
                    self.latest = (self.number, time.monotonic(), time.time_ns() // 1_000_000, frame)
                    self.condition.notify_all()
        except Exception:
            self.error = 'camera_disconnected'
        finally:
            cap.release()
            with self.condition:
                self.condition.notify_all()

    def next(self, after):
        with self.condition:
            self.condition.wait_for(lambda: self.error or (self.latest and self.latest[0] > after), timeout=1)
            if self.error:
                raise RuntimeError(self.error)
            return self.latest if self.latest and self.latest[0] > after else None

    def close(self):
        self.stop.set()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError('camera_shutdown_timeout')


def run_session(session, config, display, voice, stop, cloud, on_sample):
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from .device_health import resources
    algorithm = create_algorithm(session.meta['exercise'], session_id=session.sid,
                                 side=session.meta.get('requested_side', 'auto'))
    diagnostics = DetectionDiagnostics(session.meta)
    model = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=config['model_path'], delegate=mp.tasks.BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=.5, min_pose_presence_confidence=.5, min_tracking_confidence=.5))
    camera = None
    origin, last_frame, last_camera, last_sensor = time.monotonic(), 0, time.monotonic(), 0
    countdown = ReadyCountdown()
    reminder = TrackingReminder()
    previous_workload = session.workload_phase
    preparing, warmup_frames = True, 0
    try:
        camera = Camera(config.get('camera', 0), cv2)
        voice.say(('prepare_both_' if session.meta.get('requested_side') == 'both' else 'prepare_') + session.meta['exercise'])
        if session.meta.get('requested_side') in ('left', 'right', 'both'):
            voice.say('side_' + session.meta['requested_side'])
        while not stop.is_set():
            now = time.monotonic()
            if now - cloud.last_success >= 10:
                return 'internet_lost'
            if not display.ready:
                return 'display_disconnected'
            if not voice.ready:
                return 'audio_unavailable'
            if session.tick():
                return session.completion_reason
            if session.workload_phase != previous_workload:
                if session.workload_phase == 'aligning':
                    voice.say('set_prepare')
                    countdown.update(False, now)
                    algorithm._discard_cycle()
                previous_workload = session.workload_phase
            item = camera.next(last_frame)
            if item is None:
                display.blank()
                countdown.update(False, time.monotonic())
                if time.monotonic() - last_camera > 3:
                    return 'camera_disconnected'
                continue
            last_frame, received, epoch, frame = item
            last_camera = time.monotonic()
            if last_camera - received > .5:
                continue
            height, width = frame.shape[:2]
            sample_ms = max(1, int((received - origin) * 1000))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            prediction = model.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), sample_ms)
            warmup_frames += 1
            inference_epoch = time.time_ns() // 1_000_000
            landmarks = [[p.x, p.y, p.z, p.visibility] for p in prediction.pose_landmarks[0]] if prediction.pose_landmarks else None
            begin = time.perf_counter()
            if preparing and warmup_frames >= 5 and voice.idle():
                preparing = False
            result = algorithm.update(None if preparing else landmarks, width, height, sample_ms)
            algorithm_ms = (time.perf_counter() - begin) * 1000
            if result is None:
                continue
            # Draw only this prediction on this exact source frame. Never retain prior skeletons.
            if landmarks:
                connections = mp.solutions.pose.POSE_CONNECTIONS
                for a, b in connections:
                    pa, pb = landmarks[a], landmarks[b]
                    if min(pa[3], pb[3]) >= .5 and all(0 <= n <= 1 for n in (*pa[:2], *pb[:2])):
                        cv2.line(frame, (round(pa[0]*width), round(pa[1]*height)),
                                 (round(pb[0]*width), round(pb[1]*height)), (90, 235, 160), 3, cv2.LINE_AA)
                for x, y, _, visibility in landmarks:
                    if visibility >= .5 and 0 <= x <= 1 and 0 <= y <= 1:
                        cv2.circle(frame, (round(x*width), round(y*height)), 4, (245, 250, 250), -1, cv2.LINE_AA)
            display.offer(cv2.flip(frame, 1))
            result.update(source='camera', frame_received_epoch_ms=epoch,
                          inference_complete_epoch_ms=inference_epoch,
                          algorithm_complete_epoch_ms=time.time_ns() // 1_000_000)
            # Pre-session and per-set prompts finish before the hub starts the clock/count.
            if session.workload_phase == 'aligning':
                if result['phase'] not in ('WAIT_START', 'READY'):
                    algorithm._discard_cycle()
            elif session.workload_phase == 'resting':
                algorithm._discard_cycle()
            before_phase = session.workload_phase
            count, allow_start = countdown.update(
                session.workload_phase == 'aligning' and not preparing and voice.idle()
                and result['phase'] == 'READY' and result['tracking_status'] == 'tracking', time.monotonic())
            complete = session.sample(result, algorithm_ms=algorithm_ms,
                                      allow_start=allow_start)
            diagnostics.sample(result, preparing=preparing, countdown=count)
            if before_phase == 'aligning' and session.workload_phase == 'working':
                voice.say('set_start' if session.goal['mode'] == 'sets' else 'ready')
            if before_phase != session.workload_phase and session.workload_phase == 'resting':
                voice.say('set_rest')
                algorithm._discard_cycle()
                previous_workload = 'resting'
            on_sample(result, 'preparing' if preparing else session.phase)
            display.progress(result, 'preparing' if preparing else session.phase, count)
            if reminder.update(result['tracking_status'] == 'tracking',
                               session.workload_phase == 'working', time.monotonic()):
                voice.say('lost')
            if result.get('rep_event'):
                if session.workload_phase == 'working':
                    voice.count(result['rep_event']['rep_in_set'] if session.goal['mode'] == 'sets' else result['reps'])
            if now - last_sensor >= 2:
                sensor = resources()
                display.set_temperature(sensor['temperature_c'])
                session.sensors(sensor['temperature_c'], sensor['throttled'])
                last_sensor = now
                if sensor['temperature_c'] is not None and sensor['temperature_c'] >= 80:
                    return 'temperature_limit'
            if complete:
                return session.completion_reason
        return 'patient_stop'
    finally:
        display.blank()
        model.close()
        if camera:
            camera.close()
        # Local bounded numeric diagnostics, including frames BEFORE READY.
        # Never store camera images or landmarks and never upload this buffer.
        diagnostics.save(session.store)
