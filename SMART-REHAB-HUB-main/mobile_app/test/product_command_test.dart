import 'dart:async';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/product/api.dart';
import 'package:mobile_app/product/app.dart';

class TestUser extends Fake implements User {
  @override
  String get uid => 'patient-one';
}

class TestAuth extends Fake implements FirebaseAuth {
  @override
  User? get currentUser => TestUser();
}

class TestSnapshot extends Fake implements DataSnapshot {
  TestSnapshot(this.value);
  @override
  final Object? value;
  @override
  bool get exists => value != null;
}

class TestEvent extends Fake implements DatabaseEvent {
  TestEvent(Object? value) : snapshot = TestSnapshot(value);
  @override
  final DataSnapshot snapshot;
}

class TestDatabase extends Fake implements FirebaseDatabase {
  final ack = StreamController<DatabaseEvent>.broadcast();
  final paths = <String>[];
  final writes = <Map<String, dynamic>>[];
  bool connected = true;
  Object? offset = 12345;
  Object? writeError;
  Object? ackError;
  Map<String, Object?> acknowledgement = {
    'status': 'accepted',
    'session_id': 'session-one'
  };
  @override
  DatabaseReference ref([String? path]) => TestReference(this, path ?? '');
}

class TestReference extends Fake implements DatabaseReference {
  TestReference(this.db, this.path);
  final TestDatabase db;
  @override
  final String path;
  @override
  String? get key => path.split('/').last;
  @override
  Future<DataSnapshot> get() => throw StateError(
      'Regression: Android .info must use local listeners, not get()');
  @override
  Stream<DatabaseEvent> get onValue {
    db.paths.add(path);
    if (path == '.info/connected') return Stream.value(TestEvent(db.connected));
    if (path == '.info/serverTimeOffset') {
      return Stream.value(TestEvent(db.offset));
    }
    if (path.startsWith('rehab_v1/acks/')) return db.ack.stream;
    throw StateError('Unexpected path $path');
  }

  @override
  DatabaseReference push() => TestReference(db, '$path/command-one');
  @override
  Future<void> set(Object? value) async {
    db.writes.add(Map<String, dynamic>.from(value as Map));
    expect(db.ack.hasListener, isTrue);
    if (db.ackError != null) {
      db.ack.addError(db.ackError!);
      await Future<void>.delayed(const Duration(milliseconds: 20));
    } else if (db.writeError == null) {
      db.ack.add(TestEvent(db.acknowledgement));
    }
    if (db.writeError != null) throw db.writeError!;
  }
}

void main() {
  late TestDatabase db;
  late RehabApi api;
  setUp(() {
    db = TestDatabase();
    api = RehabApi(auth: TestAuth(), database: db);
  });
  tearDown(() async {
    await db.ack.close();
  });

  test('start reads local Firebase metadata and accepts an immediate hub ack',
      () async {
    final before = DateTime.now().millisecondsSinceEpoch;
    final result =
        await api.command('hub-one', 'start', exercise: 'squat', duration: 180);
    expect(result['session_id'], 'session-one');
    expect(db.paths.take(2), ['.info/connected', '.info/serverTimeOffset']);
    expect(db.writes.single['patient_uid'], 'patient-one');
    expect(db.writes.single['created_at'], ServerValue.timestamp);
    expect(db.writes.single['expires_at'],
        greaterThanOrEqualTo(before + 12345 + 29000));
    expect(db.writes.single['exercise'], 'squat');
    expect(db.ack.hasListener, isFalse);
  });

  test('protocol 2 sends fixed body side and set goal without legacy duration',
      () async {
    await api.command('hub-one', 'start',
        exercise: 'shoulder_flexion',
        requestedSide: 'right',
        goal: {'mode': 'sets', 'reps_per_set': 10, 'sets': 3, 'rest_s': 45});
    expect(db.writes.single['protocol_version'], 2);
    expect(db.writes.single['requested_side'], 'right');
    expect(db.writes.single['goal'],
        {'mode': 'sets', 'reps_per_set': 10, 'sets': 3, 'rest_s': 45});
    expect(db.writes.single.containsKey('duration_s'), isFalse);
  });
  test('invalid protocol 2 goal or automatic unilateral side never writes',
      () async {
    await expectLater(
        api.command('hub-one', 'start',
            exercise: 'shoulder_flexion',
            requestedSide: 'auto',
            goal: {'mode': 'time', 'duration_s': 60}),
        throwsFormatException);
    expect(db.writes, isEmpty);
  });

  test('offline phone never sends a command', () async {
    db.connected = false;
    await expectLater(
        api.command('hub-one', 'start'), throwsA(isA<StateError>()));
    expect(db.writes, isEmpty);
  });

  test('unknown server clock never sends a command with a guessed deadline',
      () async {
    db.offset = null;
    await expectLater(
        api.command('hub-one', 'start'), throwsA(isA<StateError>()));
    expect(db.writes, isEmpty);
  });

  test('stop carries the actual session id and omits start-only fields',
      () async {
    await api.command('hub-one', 'stop', sessionId: 'session-one');
    expect(db.writes.single['session_id'], 'session-one');
    expect(db.writes.single.containsKey('exercise'), isFalse);
    expect(db.writes.single.containsKey('duration_s'), isFalse);
  });

  test('hub rejection is reported without claiming the session started',
      () async {
    db.acknowledgement = {'status': 'rejected', 'reason': 'camera_unavailable'};
    await expectLater(
        api.command('hub-one', 'start'), throwsA(isA<StateError>()));
    expect(db.ack.hasListener, isFalse);
  });

  test('write permission failure releases acknowledgement subscription',
      () async {
    db.writeError = FirebaseException(
        plugin: 'firebase_database', code: 'permission-denied');
    await expectLater(
        api.command('hub-one', 'start'), throwsA(isA<FirebaseException>()));
    expect(db.ack.hasListener, isFalse);
  });

  test('early acknowledgement error is handled while write is still pending',
      () async {
    db.ackError = FirebaseException(
        plugin: 'firebase_database', code: 'permission-denied');
    await expectLater(
        api.command('hub-one', 'start'), throwsA(isA<FirebaseException>()));
    expect(db.ack.hasListener, isFalse);
    await Future<void>.delayed(const Duration(milliseconds: 30));
  });

  test(
      'database permission errors no longer masquerade as data-loading failures',
      () {
    final error = FirebaseException(
        plugin: 'firebase_database', code: 'permission-denied');
    expect(readableError(error), contains('quyền'));
    expect(readableError(error), isNot(contains('Chưa tải được dữ liệu')));
  });
}
