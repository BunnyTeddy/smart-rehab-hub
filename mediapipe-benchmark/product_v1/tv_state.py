"""Private, local TV presentation. No patient identifiers or new cloud fields."""
import math
import re
from .catalog import EXERCISE_CATALOG

SIDES = {'left': 'Bên trái', 'right': 'Bên phải', 'both': 'Cả hai cùng lúc', 'auto': ''}
ERRORS = {
    'internet_lost': 'Mất kết nối Internet. Kiểm tra mạng rồi mở buổi tập mới.',
    'camera_disconnected': 'Webcam bị ngắt. Kiểm tra dây cắm webcam.',
    'camera_unavailable': 'Chưa mở được webcam. Kiểm tra dây cắm webcam.',
    'camera_shutdown_timeout': 'Webcam chưa phản hồi. Kiểm tra dây cắm trước khi tập lại.',
    'display_disconnected': 'Màn hình bị ngắt kết nối trong buổi tập.',
    'audio_unavailable': 'Âm thanh chưa sẵn sàng. Kiểm tra loa của hub.',
    'temperature_limit': 'Hub đang nóng. Chờ thiết bị nguội và kiểm tra thông gió.',
    'storage_unavailable': 'Chưa ghi được dữ liệu. Kiểm tra bộ nhớ của hub.',
    'preparation_timeout': 'Hết thời gian căn người. Chỉnh webcam rồi thử lại.',
    'session_limit': 'Đã hết 30 phút; mục tiêu các hiệp chưa hoàn thành.',
    'hub_restarted': 'Hub đã khởi động lại. Buổi tập trước đã dừng.',
    'hub_shutdown': 'Hub đã dừng hoạt động trong buổi tập.',
}


def duration(value):
    seconds = max(0, math.ceil(value or 0))
    return f'{seconds // 60}:{seconds % 60:02d}'


def detection_hint(sample, exercise):
    reason = re.sub(r'^(left|right):', '', sample.get('reason') or '')
    joint = re.fullmatch(r'landmark_(\d+)_(.+)', reason)
    if joint:
        name = {11: 'vai trái', 12: 'vai phải', 13: 'khuỷu tay trái', 14: 'khuỷu tay phải',
                15: 'cổ tay trái', 16: 'cổ tay phải', 23: 'hông trái', 24: 'hông phải',
                25: 'gối trái', 26: 'gối phải', 27: 'cổ chân trái', 28: 'cổ chân phải'}.get(int(joint[1]), 'khớp cần đo')
        return (f'Đưa {name} vào khung hình.' if joint[2] == 'out_of_frame'
                else f'Để webcam nhìn rõ {name}.')
    hints = {
        'missing_pose': 'Đứng hoặc ngồi vào khung hình, ở nơi đủ sáng.',
        'out_of_frame': 'Lùi lại một chút để thấy đủ các khớp cần đo.',
        'low_visibility': 'Tránh để tay, chân hoặc đồ vật che khớp đang tập.',
        'trunk_guard': 'Giữ thân thẳng, tránh nghiêng người theo động tác.',
        'elbow_guard': 'Giữ khuỷu gần thẳng khi nâng tay.',
        'hip_guard': 'Giữ tư thế ngồi và đùi tương đối yên.',
        'knee_guard': 'Giữ gối gập khi nâng đùi.' if exercise == 'seated_hip_flexion' else 'Giữ chân tập tương đối thẳng.',
        'support_leg_guard': 'Giữ chân trụ thẳng và vịn điểm tựa chắc.',
        'camera_view_guard': 'Đặt webcam chính diện để thấy rõ hai bên.',
        'inward_movement': 'Đưa tay hoặc chân ra bên ngoài cơ thể.',
        'both_not_in_same_zone': 'Tập cùng nhịp; cả hai cùng về tư thế đầu.',
        'gap_reset': 'Hình ảnh ngắt quãng. Về tư thế đầu để tập tiếp.',
        'selecting_side': 'Giữ tư thế đầu để hub chọn bên nhìn rõ.',
    }
    if reason in hints:
        return hints[reason]
    phase = sample.get('phase')
    if phase == 'WAIT_START':
        return EXERCISE_CATALOG.get(exercise, {}).get('steps', ['Về tư thế đầu và giữ yên một nhịp.'])[0]
    if phase in ('AT_TARGET', 'RETURNING'):
        return 'Trở về tư thế đầu để hoàn thành một lần.'
    if phase == 'OUTBOUND':
        return 'Tiếp tục động tác trong mức thoải mái.'
    return 'Tập chậm và đều theo hướng dẫn.'


class ReadyCountdown:
    """Three continuous READY seconds AFTER speech. Loss cancels, never pauses."""
    def __init__(self):
        self.since = None

    def update(self, eligible, now):
        if not eligible:
            self.since = None
            return None, False
        if self.since is None:
            self.since = now
        left = max(0, 3 - (now - self.since))
        return (math.ceil(left) if left > 0 else None), left == 0


class TVPresentation:
    """Called under Display's lock; only allowlisted, non-identifying data retained."""
    def __init__(self, now):
        self.mode, self.idle_since = 'idle', now
        self.meta, self.sample, self.summary = {}, {}, {}
        self.countdown, self.summary_until = None, 0

    def begin(self, meta):
        self.meta = {k: meta.get(k) for k in ('exercise', 'requested_side', 'goal')}
        self.mode, self.sample, self.summary, self.countdown = 'preparing', {}, {}, None

    def progress(self, sample, phase, countdown=None):
        if self.mode in ('idle', 'summary', 'stopping'):
            return
        self.mode = 'preparing' if phase == 'preparing' else sample.get('workload_phase', 'aligning')
        self.sample = {k: sample.get(k) for k in ('phase', 'reason', 'tracking_status', 'reps',
                      'set_number', 'rep_in_set', 'remaining_s', 'rest_remaining_s')}
        self.countdown = countdown

    def finish(self, summary, now):
        self.summary = {k: summary.get(k) for k in ('exercise', 'error', 'reps', 'active_s',
                        'elapsed_s', 'completed_sets', 'goal')}
        self.meta, self.sample, self.countdown = {}, {}, None
        self.mode, self.summary_until, self.idle_since = 'summary', now + 15, now + 15

    def view(self, now, health, camera_fresh):
        if self.mode == 'summary' and now >= self.summary_until:
            self.mode, self.summary = 'idle', {}
        online = bool(health.get('online'))
        if self.mode == 'idle':
            title, hint, accent = 'Sẵn sàng tập luyện', 'Mở SMART REHAB trên điện thoại để chọn bài.', 'mint'
            if health.get('storage_fault'):
                title, hint, accent = 'Hub cần được kiểm tra', ERRORS['storage_unavailable'], 'amber'
            elif not online:
                title, hint, accent = 'Đang kết nối Internet', 'Kiểm tra mạng của hub trên ứng dụng điện thoại.', 'amber'
            elif not health.get('paired'):
                title, hint = 'Chào mừng bạn', 'Mở SMART REHAB trên điện thoại để ghép hub.'
            elif not health.get('audio_ready'):
                title, hint, accent = 'Âm thanh chưa sẵn sàng', ERRORS['audio_unavailable'], 'amber'
            return dict(mode='idle', title=title, hint=hint, accent=accent,
                        status='Đã kết nối Internet' if online else 'Chưa kết nối Internet',
                        dim=now-self.idle_since >= 180, drift=int(max(0, now-self.idle_since)//60)%3)
        if self.mode == 'summary':
            s = self.summary
            success = s.get('error') in ('goal_complete', 'duration_complete')
            title = 'Hoàn thành buổi tập' if success else 'Buổi tập đã dừng'
            goal = s.get('goal') or {}
            return dict(mode='summary', title=title, accent='mint' if success else 'amber',
                        success=success, reason=s.get('error'),
                        exercise=EXERCISE_CATALOG.get(s.get('exercise'), {}).get('name', ''),
                        hint=('Bạn có thể xem chi tiết trong ứng dụng.' if success or s.get('error') == 'patient_stop'
                              else ERRORS.get(s.get('error'), 'Buổi tập bị gián đoạn. Kiểm tra hub rồi thử lại.')),
                        reps=str(s.get('reps') or 0), time=duration(s.get('active_s') if s.get('active_s') is not None else s.get('elapsed_s')),
                        sets=f"{s.get('completed_sets') or 0}/{goal.get('sets', 1)}" if goal.get('mode') == 'sets' else '—',
                        return_in=math.ceil(self.summary_until-now), offline=not online)
        e, s, goal = self.meta.get('exercise'), self.sample, self.meta.get('goal') or {}
        mode = self.mode
        heading = {'preparing': 'Đang chuẩn bị', 'aligning': 'Căn lại tư thế', 'working': 'Đang tập',
                   'resting': 'Nghỉ giữa hiệp', 'complete': 'Đang lưu kết quả', 'stopping': 'Đang dừng buổi tập'}.get(mode, 'Đang chuẩn bị')
        hint = detection_hint(s, e)
        accent, countdown = 'mint', self.countdown
        if mode == 'preparing':
            hint = 'Nghe hướng dẫn và đưa người vào khung hình.'
        elif mode == 'resting':
            hint = f"Thả lỏng. Tiếp theo: hiệp {(s.get('set_number') or 1)+1}/{goal.get('sets', 1)}."
        elif mode == 'stopping':
            hint = 'Hub đang kết thúc và lưu buổi tập.'
        elif countdown is not None:
            heading, hint = 'Sẵn sàng', 'Giữ tư thế đầu, buổi tập sắp bắt đầu.'
        # Connectivity warnings take priority, but never imply the session already stopped.
        if not online:
            heading, hint, accent, countdown = 'Kết nối đang gián đoạn', 'Hub sẽ dừng nếu mất Internet liên tục 10 giây.', 'amber', None
        elif not camera_fresh and mode not in ('preparing', 'stopping', 'complete'):
            heading, hint, accent, countdown = 'Đang chờ webcam', 'Chưa có hình mới. Kiểm tra dây cắm webcam.', 'amber', None
        elif mode in ('aligning', 'working') and s.get('tracking_status') != 'tracking':
            accent = 'amber'
            if mode == 'working':
                heading = 'Chưa thấy rõ khớp'
        progress = (f"Hiệp {s.get('set_number') or 1}/{goal.get('sets', 1)}" if goal.get('mode') == 'sets'
                    else 'Thời gian còn lại')
        number = (f"{s.get('rep_in_set') or 0}/{goal.get('reps_per_set', 5)}" if goal.get('mode') == 'sets'
                  else duration(s.get('remaining_s', goal.get('duration_s', 180))))
        if mode == 'resting':
            progress, number = 'Nghỉ còn lại', duration(s.get('rest_remaining_s'))
        if countdown is not None:
            progress, number = 'Bắt đầu sau', str(countdown)
        return dict(mode=mode, exercise=EXERCISE_CATALOG.get(e, {}).get('name', ''),
                    motion_phase=s.get('phase'),
                    side=SIDES.get(self.meta.get('requested_side'), ''), title=heading, hint=hint,
                    accent=accent, progress=progress, number=number, countdown=countdown,
                    reps=str(s.get('reps') or 0), camera_fresh=camera_fresh)
