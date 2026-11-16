import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/workout_session.dart';

Map<String, Object?> fixture(
        {String session = 's1',
        int seq = 1,
        String exercise = 'biceps_curl',
        String tracking = 'tracking',
        double? angle = 160,
        int reps = 0,
        int timestamp = 100000}) =>
    {
      'schema_version': 2,
      'session_id': session,
      'exercise': exercise,
      'sequence': seq,
      'sample_timestamp_ms': seq * 100,
      'timestamp': timestamp,
      'side': 'left',
      'phase': 'READY',
      'reps': reps,
      'angle': angle,
      'tracking_status': tracking,
      'form_status': 'not_evaluated',
    };

void main() {
  test('five canonical exercise IDs, no lateral raise alias', () {
    for (final id in exerciseNames.keys) {
      expect(WorkoutSample.parse(fixture(exercise: id), 's1')?.exercise, id);
    }
    expect(
        WorkoutSample.parse(fixture(exercise: 'lateral_raise'), 's1'), isNull);
    expect(WorkoutSample.parse(fixture(session: 'someone_else'), 's1'), isNull);
  });
  test('null angle allowed only when not tracking; malformed packets rejected',
      () {
    expect(
        WorkoutSample.parse(fixture(tracking: 'lost', angle: null), 's1')
            ?.angle,
        isNull);
    expect(WorkoutSample.parse(fixture(angle: null), 's1'), isNull);
    expect(WorkoutSample.parse(fixture(angle: double.nan), 's1'), isNull);
    expect(WorkoutSample.parse(fixture()..['form_status'] = 'correct', 's1'),
        isNull);
    expect(validSessionId('../other'), isFalse);
  });
  test('accept, stale after 2s, old cached packet remains stale', () async {
    var now = DateTime.fromMillisecondsSinceEpoch(100000);
    final stream = StreamController<Object?>();
    final c =
        WorkoutSessionController(source: (_) => stream.stream, now: () => now);
    await c.bind('s1');
    stream.add(fixture());
    await Future<void>.delayed(Duration.zero);
    expect(c.status, 'tracking');
    now = now.add(const Duration(seconds: 2));
    expect(c.status, 'stale');
    stream.add(fixture(seq: 2));
    await Future<void>.delayed(Duration.zero);
    expect(c.status, 'stale');
    await c.close();
    c.dispose();
    await stream.close();
  });
  test('wrong session, exercise changes and duplicate sequence rejected',
      () async {
    final stream = StreamController<Object?>();
    final c = WorkoutSessionController(
        source: (_) => stream.stream,
        now: () => DateTime.fromMillisecondsSinceEpoch(100000));
    await c.bind('s1');
    stream.add(fixture());
    await Future<void>.delayed(Duration.zero);
    stream.add(fixture(seq: 1, reps: 4));
    await Future<void>.delayed(Duration.zero);
    expect(c.sample?.reps, 0);
    stream.add(fixture(seq: 2, session: 's2'));
    await Future<void>.delayed(Duration.zero);
    expect(c.sample?.sessionId, 's1');
    expect(c.status, 'error');
    stream.add(fixture(seq: 3, exercise: 'squat'));
    await Future<void>.delayed(Duration.zero);
    expect(c.sample?.exercise, 'biceps_curl');
    expect(c.status, 'error');
    c.dispose();
    await stream.close();
  });
  test('bind and dispose cancel previous streams', () async {
    var cancellations = 0;
    final streams = <StreamController<Object?>>[];
    final c = WorkoutSessionController(source: (_) {
      final s = StreamController<Object?>(onCancel: () => cancellations++);
      streams.add(s);
      return s.stream;
    });
    await c.bind('s1');
    await c.bind('s2');
    expect(cancellations, 1);
    c.dispose();
    await Future<void>.delayed(Duration.zero);
    expect(cancellations, 2);
    for (final s in streams) {
      await s.close();
    }
  });
}
