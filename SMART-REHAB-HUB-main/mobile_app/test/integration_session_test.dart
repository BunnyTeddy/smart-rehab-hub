import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/workout_session.dart';
import 'workout_session_test.dart' show fixture;

void main() {
  test('old frame remains stale after a fresh send timestamp', () async {
    final stream = StreamController<Object?>();
    final controller = WorkoutSessionController(source: (_) => stream.stream,
        now: () => DateTime.fromMillisecondsSinceEpoch(100000));
    await controller.bind('s1');
    stream.add(fixture()..['frame_received_epoch_ms'] = 97000);
    await Future<void>.delayed(Duration.zero);
    expect(controller.status, 'stale');
    controller.dispose(); await stream.close();
  });
  test('summary exact session ends stream; all listeners cancelled', () async {
    var cancellations=0;
    final samples=StreamController<Object?>(onCancel:()=>cancellations++);
    final summaries=StreamController<Object?>(onCancel:()=>cancellations++);
    final connection=StreamController<bool>(onCancel:()=>cancellations++);
    final controller=WorkoutSessionController(source:(_)=>samples.stream,
        summarySource:(_)=>summaries.stream, connectionSource:connection.stream,
        now:()=>DateTime.fromMillisecondsSinceEpoch(100000));
    await controller.bind('s1');
    samples.add(fixture());connection.add(true);
    await Future<void>.delayed(Duration.zero);
    summaries.add({'session_id':'s1','exercise':'biceps_curl','reps':3,'ended_at':100001,'status':'completed'});
    await Future<void>.delayed(Duration.zero);
    expect(controller.status,'ended');expect(controller.summary?['reps'],3);expect(controller.connected,true);
    samples.add(fixture(seq:2,reps:8));await Future<void>.delayed(Duration.zero);
    expect(controller.summary?['reps'],3);
    expect(controller.timings,isNotEmpty);
    await controller.close();expect(cancellations,3);expect(controller.summary,isNull);
    expect(controller.timings,isEmpty);expect(controller.sample,isNull);expect(controller.sessionId,isNull);
    controller.dispose();await samples.close();await summaries.close();await connection.close();
  });
  test('wrong session summary rejected', () async {
    final samples=StreamController<Object?>(), summaries=StreamController<Object?>();
    final controller=WorkoutSessionController(source:(_)=>samples.stream,summarySource:(_)=>summaries.stream);
    await controller.bind('s1');
    summaries.add({'session_id':'s2','exercise':'squat','reps':4,'ended_at':1,'status':'completed'});
    await Future<void>.delayed(Duration.zero);
    expect(controller.status,'error');expect(controller.summary,isNull);
    controller.dispose();await samples.close();await summaries.close();
  });
}
