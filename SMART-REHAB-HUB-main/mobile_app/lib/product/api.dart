import 'dart:async';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'contract.dart';

class RehabApi {
  final FirebaseAuth auth;
  final FirebaseDatabase database;
  RehabApi({FirebaseAuth? auth, FirebaseDatabase? database})
      : auth = auth ?? FirebaseAuth.instance,
        database = database ?? FirebaseDatabase.instance;
  String get uid => auth.currentUser!.uid;
  DatabaseReference ref(String path) => database.ref('$productRoot/$path');
  Stream<Map<String, dynamic>> watch(String path) =>
      ref(path).onValue.map((event) => asMap(event.snapshot.value));
  Stream<bool> get connection => database
      .ref('.info/connected')
      .onValue
      .map((e) => e.snapshot.value == true);
  Stream<String?> get hubId =>
      ref('patientHub/$uid').onValue.map((e) => e.snapshot.value as String?);
  Stream<List<Map<String, dynamic>>> get history => ref('patientSessions/$uid')
          .orderByChild('created_at')
          .limitToLast(100)
          .onValue
          .map((e) {
        final values = asMap(e.snapshot.value).values.map(asMap).toList();
        values.sort((a, b) =>
            number(b['created_at']).compareTo(number(a['created_at'])));
        return values;
      });

  Future<void> requirePatient() async {
    final token = await auth.currentUser!.getIdTokenResult(true);
    if (token.claims?['role'] != null && token.claims?['role'] != 'patient') {
      await auth.signOut();
      throw StateError('Ứng dụng này dành cho tài khoản bệnh nhân.');
    }
  }

  Future<void> saveProfile(String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty || trimmed.length > 100) {
      throw StateError('Nhập tên từ 1 đến 100 ký tự.');
    }
    await ref('patients/$uid/profile').set({
      'name': trimmed,
      'updated_at': ServerValue.timestamp,
    }).timeout(const Duration(seconds: 15));
  }

  Future<Map<String, dynamic>> command(String hub, String action,
      {String? exercise,
      int? duration,
      String? sessionId,
      String? requestedSide,
      Map<String, dynamic>? goal}) async {
    if (action == 'start' && goal != null) {
      validateWorkoutGoal(exercise ?? '', requestedSide ?? '', goal);
    }
    // .info values belong to the native SDK's local info tree. Android get()
    // queries the server tree instead, which rejects these special paths.
    Future<Object?> localInfo(String path) async {
      try {
        return (await database
                .ref(path)
                .onValue
                .first
                .timeout(const Duration(seconds: 8)))
            .snapshot
            .value;
      } on TimeoutException {
        throw StateError(
            'Chưa xác nhận được kết nối với máy chủ. Yêu cầu chưa được gửi, bạn thử lại nhé.');
      }
    }

    final connected = await localInfo('.info/connected') == true;
    if (!connected) {
      throw StateError('Điện thoại đang mất mạng. Yêu cầu chưa được gửi.');
    }
    final clock = await localInfo('.info/serverTimeOffset');
    if (clock is! num || !clock.isFinite) {
      throw StateError(
          'Chưa đồng bộ được giờ với máy chủ. Yêu cầu chưa được gửi, bạn thử lại nhé.');
    }
    final offset = clock.toInt();
    final now = DateTime.now().millisecondsSinceEpoch + offset;
    final command = ref('commands/$hub').push();
    final ack = ref('acks/$hub/${command.key}');
    // Subscribe before writing so a fast acknowledgement cannot be missed.
    final completed = Completer<Map<String, dynamic>>();
    final subscription = ack.onValue.listen((e) {
      if (e.snapshot.exists && !completed.isCompleted) {
        completed.complete(asMap(e.snapshot.value));
      }
    }, onError: (Object error) {
      if (!completed.isCompleted) completed.completeError(error);
    });
    try {
      // Observe both failures immediately: a denied ack can arrive before the
      // command write completes and must not become an unhandled async error.
      final outcomes = await Future.wait<Object?>([
        command.set({
          'action': action,
          'patient_uid': uid,
          'created_at': ServerValue.timestamp,
          'expires_at': now + 29000,
          if (action == 'start') ...{
            'exercise': exercise,
            if (goal == null) 'duration_s': duration,
            if (goal != null) ...{
              'protocol_version': 2,
              'requested_side': requestedSide,
              'goal': goal
            }
          },
          if (action == 'stop') 'session_id': sessionId,
        }).timeout(const Duration(seconds: 10)),
        completed.future.timeout(const Duration(seconds: 32)),
      ], eagerError: true);
      final result = outcomes[1] as Map<String, dynamic>;
      if (result['status'] != 'accepted') {
        throw StateError(reasonText(result['reason']));
      }
      return result;
    } on TimeoutException {
      throw StateError(
          'Chưa nhận được xác nhận của hub. Trạng thái sẽ tự cập nhật khi có kết nối; đừng bắt đầu thêm phiên mới.');
    } finally {
      await subscription.cancel();
      if (!completed.isCompleted) completed.complete({});
    }
  }

  Future<void> linkDoctor(String doctor) async {
    final directory = await ref('doctorDirectory/$doctor').get();
    if (!directory.exists) throw StateError('Mã bác sĩ này chưa được đăng ký.');
    await ref('').update(
        {'careLinks/$doctor/$uid': true, 'patientDoctors/$uid/$doctor': true});
  }

  Future<void> revokeDoctor(String doctor) => ref('').update(
      {'careLinks/$doctor/$uid': null, 'patientDoctors/$uid/$doctor': null});
}
