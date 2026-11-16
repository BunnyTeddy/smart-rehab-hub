import 'dart:convert';

export 'catalog.g.dart';
import 'catalog.g.dart';

const productRoot = 'rehab_v1';
const serviceUuid = '8273ed51-236b-4f1d-80ce-507265686162';
const challengeUuid = '8273ed52-236b-4f1d-80ce-507265686162';
const requestUuid = '8273ed53-236b-4f1d-80ce-507265686162';
const responseUuid = '8273ed54-236b-4f1d-80ce-507265686162';

Map<String, dynamic> asMap(dynamic value) => value is Map
    ? value.map((key, value) => MapEntry(key.toString(), value))
    : {};
num number(dynamic value) => value is num && value.isFinite ? value : 0;
String exerciseName(dynamic value) => exerciseNames[value] ?? 'Bài tập';
String durationText(dynamic seconds) {
  final total = number(seconds).round();
  return '${total ~/ 60}:${(total % 60).toString().padLeft(2, '0')}';
}

String dateText(dynamic timestamp) {
  if (timestamp is! num || timestamp <= 0) return 'Chưa có thời gian';
  final d = DateTime.fromMillisecondsSinceEpoch(timestamp.toInt()).toLocal();
  return '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year} · ${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
}

String reasonText(dynamic code) =>
    const {
      'goal_complete': 'Đã hoàn thành đủ các hiệp đã chọn',
      'session_limit': 'Đã hết 30 phút; chưa hoàn thành mục tiêu',
      'invalid_goal': 'Mục tiêu tập chưa hợp lệ. Bạn chọn lại nhé.',
      'invalid_requested_side': 'Hãy chọn bên tập được bài này hỗ trợ.',
      'unsupported_protocol': 'Hub cần được cập nhật để dùng chế độ này.',
      'duration_complete': 'Đã hoàn thành thời lượng đã chọn',
      'patient_stop': 'Bạn đã dừng buổi tập',
      'internet_lost': 'Hub mất kết nối Internet',
      'hub_restarted': 'Hub đã khởi động lại',
      'hub_shutdown': 'Hub đã tắt',
      'camera_disconnected': 'Webcam bị ngắt kết nối',
      'camera_unavailable': 'Chưa kết nối được webcam',
      'camera_shutdown_timeout': 'Webcam chưa đóng được',
      'preparation_timeout': 'Chưa nhận được tư thế sẵn sàng',
      'temperature_limit': 'Hub cần nghỉ để giảm nhiệt',
      'display_unavailable': 'Hãy bật TV và kiểm tra dây HDMI',
      'display_disconnected': 'TV đã ngắt kết nối',
      'audio_unavailable': 'Âm thanh của hub chưa sẵn sàng',
      'storage_unavailable': 'Hub cần được kiểm tra bộ nhớ',
      'hub_offline': 'Hub chưa kết nối Internet',
      'session_already_active': 'Hub đang có một buổi tập',
      'session_not_active': 'Buổi tập này đã kết thúc',
      'command_expired': 'Yêu cầu đã hết hạn. Bạn thử lại nhé.',
      'wifi_connection_failed':
          'Chưa kết nối được Wi-Fi. Kiểm tra tên mạng và mật khẩu.',
      'wifi_connection_timeout': 'Kết nối Wi-Fi quá lâu. Bạn thử lại nhé.',
      'invalid_wifi_password': 'Mật khẩu Wi-Fi cần từ 8 đến 63 ký tự.',
      'invalid_ssid': 'Tên Wi-Fi chưa hợp lệ.',
      'hub_has_another_owner': 'Hub này đã thuộc về một tài khoản khác.',
      'patient_has_another_hub': 'Tài khoản của bạn đã ghép với một hub khác.',
      'patient_verification_failed':
          'Chưa xác minh được tài khoản. Kiểm tra Internet và đăng nhập lại.',
      'wifi_restore_pending':
          'Chưa khôi phục được mạng cũ. Giữ hub bật và thử kết nối lại.',
      'session_active': 'Hãy dừng buổi tập trước khi đổi Wi-Fi.',
      'provisioning_active': 'Hub đang cài đặt Wi-Fi. Vui lòng chờ.',
    }[code] ??
    'Hub chưa hoàn tất yêu cầu. Bạn kiểm tra kết nối và thử lại nhé.';

class SetupQr {
  final String type, id;
  final String? key;
  SetupQr(this.type, this.id, this.key);
  factory SetupQr.parse(String text, String expectedType) {
    final value = asMap(jsonDecode(text));
    final type = value['type'];
    final id = value[type == 'hub' ? 'hub_id' : 'doctor_uid'];
    if (value['v'] != 1 ||
        type != expectedType ||
        id is! String ||
        !RegExp(r'^[A-Za-z0-9_-]{1,100}$').hasMatch(id)) {
      throw const FormatException('Mã QR không đúng loại hoặc chưa hợp lệ.');
    }
    final key = value['key'];
    if (type == 'hub' && (key is! String || base64Decode(key).length != 32)) {
      throw const FormatException('Mã ghép hub chưa hợp lệ.');
    }
    return SetupQr(type, id, key as String?);
  }
}

String sideText(dynamic side) =>
    const {
      'left': 'Bên trái',
      'right': 'Bên phải',
      'both': 'Cả hai cùng lúc',
      'auto': 'Tự chọn bên nhìn rõ'
    }[side] ??
    'Chưa chọn bên đo';
String goalText(dynamic value) {
  final g = asMap(value);
  return g['mode'] == 'sets'
      ? '${number(g['reps_per_set']).toInt()} lần × ${number(g['sets']).toInt()} hiệp'
      : g['mode'] == 'time'
          ? '${number(g['duration_s']).toInt() ~/ 60} phút'
          : 'Theo thời gian';
}

String phaseText(dynamic value) =>
    const {
      'aligning': 'Căn người để sẵn sàng',
      'working': 'Đang tập',
      'resting': 'Đang nghỉ giữa hiệp',
      'complete': 'Đang lưu kết quả'
    }[value] ??
    'Đang chuẩn bị';
bool supportsProtocol2(Map<String, dynamic> state) =>
    asMap(state['capabilities'])['protocol_version'] == 2;
bool supportsExercise(Map<String, dynamic> state, String id) =>
    isExerciseAvailable(id) &&
    (supportsProtocol2(state)
        ? asMap(asMap(state['capabilities'])['exercises'])[id] == true
        : ['squat', 'biceps_curl'].contains(id));
bool supportsBoth(Map<String, dynamic> state, String id) =>
    isExerciseAvailable(id) &&
    supportsProtocol2(state) &&
    exerciseDetails(id)['bilateral'] == true &&
    asMap(asMap(state['capabilities'])['bilateral'])[id] == true;
void validateWorkoutGoal(
    String exercise, String side, Map<String, dynamic> goal) {
  final e = exerciseDetails(exercise);
  if (!isExerciseAvailable(exercise) ||
      e.isEmpty ||
      (e['side_mode'] == 'required'
          ? !(e['bilateral'] == true
                  ? ['left', 'right', 'both']
                  : ['left', 'right'])
              .contains(side)
          : side != 'auto')) {
    throw const FormatException('Chọn bài và bên tập hợp lệ.');
  }
  bool integer(dynamic n) => n is int;
  final d = goal['duration_s'],
      r = goal['reps_per_set'],
      n = goal['sets'],
      rest = goal['rest_s'];
  final time = goal['mode'] == 'time' &&
      goal.length == 2 &&
      integer(d) &&
      d >= 60 &&
      d <= 600 &&
      d % 60 == 0;
  final sets = goal['mode'] == 'sets' &&
      goal.length == 4 &&
      integer(r) &&
      [5, 10, 15].contains(r) &&
      integer(n) &&
      [1, 2, 3].contains(n) &&
      integer(rest) &&
      rest >= 15 &&
      rest <= 120 &&
      rest % 15 == 0;
  if (!time && !sets) throw const FormatException('Chọn mục tiêu tập hợp lệ.');
}

String detectionHint(Map<String, dynamic> sample, String exercise) {
  final reason = (sample['reason'] ?? '')
      .toString()
      .replaceFirst(RegExp(r'^(left|right):'), '');
  final landmark = RegExp(r'^landmark_(\d+)_(.+)$').firstMatch(reason);
  if (landmark != null) {
    final name = const {
      11: 'vai trái',
      12: 'vai phải',
      13: 'khuỷu tay trái',
      14: 'khuỷu tay phải',
      15: 'cổ tay trái',
      16: 'cổ tay phải',
      23: 'hông trái',
      24: 'hông phải',
      25: 'gối trái',
      26: 'gối phải',
      27: 'cổ chân trái',
      28: 'cổ chân phải'
    }[int.tryParse(landmark.group(1)!)];
    return landmark.group(2) == 'out_of_frame'
        ? '${name ?? 'Khớp cần đo'} đang ngoài khung hình. Bạn lùi lại hoặc chỉnh webcam nhé.'
        : 'Chưa thấy rõ ${name ?? 'khớp cần đo'}. Kiểm tra bên đang tập và tránh để khớp bị che.';
  }
  final specific = {
    'missing_pose':
        'Chưa tìm thấy người trong hình. Kiểm tra webcam, ánh sáng và đứng/ngồi vào khung hình.',
    'out_of_frame':
        'Một khớp cần đo đang ngoài khung hình. Bạn lùi lại hoặc chỉnh webcam nhé.',
    'low_visibility':
        'Khớp đang bị che hoặc khó nhìn rõ. Kiểm tra bên tập và hướng webcam.',
    'trunk_guard':
        'Giữ thân thẳng và đặt webcam cân bằng, tránh nghiêng người theo tay hoặc chân.',
    'elbow_guard': 'Giữ khuỷu tay gần thẳng khi nâng tay theo hướng dẫn.',
    'hip_guard': 'Giữ tư thế ngồi, đùi tương đối yên khi duỗi gối.',
    'knee_guard': exercise == 'seated_hip_flexion'
        ? 'Giữ gối gập khi nâng đùi; tránh duỗi chân ra trước.'
        : 'Giữ chân tập tương đối thẳng khi đưa sang bên.',
    'support_leg_guard': 'Giữ chân trụ tương đối thẳng và vịn điểm tựa.',
    'camera_view_guard':
        'Đặt webcam chính diện để thấy rõ hai vai hoặc hai hông.',
    'inward_movement':
        'Đưa tay/chân ra ngoài bên cơ thể, tránh bắt chéo vào trong.',
    'both_not_in_same_zone':
        'Hai bên chưa cùng vị trí trong động tác. Tập cùng nhịp; cả hai cùng trở về mới tính một lần.',
    'gap_reset':
        'Hình ảnh bị ngắt quãng. Về tư thế đầu để bắt đầu lại lần này.',
    'selecting_side':
        'Đang chọn bên nhìn rõ. Đưa các khớp cần đo vào khung hình.'
  }[reason];
  if (specific != null) return specific;
  if (sample['workload_phase'] == 'aligning' && sample['phase'] == 'READY') {
    return 'Giữ tư thế này, chờ đếm ngược trên TV rồi bắt đầu tập.';
  }
  if (sample['phase'] == 'WAIT_START') {
    final steps = exerciseDetails(exercise)['steps'] as List?;
    return 'Về tư thế đầu và giữ yên một nhịp. ${steps?.first ?? ''}';
  }
  if (sample['phase'] == 'AT_TARGET' || sample['phase'] == 'RETURNING') {
    return 'Đã nhận chiều đi. Trở về tư thế đầu để hoàn thành một lần.';
  }
  return sample['phase'] == 'OUTBOUND'
      ? 'Đang nhận chiều đi của động tác. Tập theo hướng dẫn trong mức thoải mái.'
      : 'Đã nhận tư thế đầu. Bạn có thể tập theo hướng dẫn.';
}
