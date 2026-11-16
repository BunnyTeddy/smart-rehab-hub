import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/home_screen.dart';
import 'package:mobile_app/workout_session.dart';
import 'workout_session_test.dart' show fixture;

void main() {
  testWidgets('summary before latest still displays correct exercise and reps', (tester) async {
    final samples = StreamController<Object?>(), summaries = StreamController<Object?>();
    final controller = WorkoutSessionController(source: (_) => samples.stream,
        summarySource: (_) => summaries.stream);
    await tester.pumpWidget(MaterialApp(home: HomeScreen(userName:'Test',
        sessionId:'s1',demo:true,sessionController:controller)));
    await tester.pumpAndSettle();
    summaries.add({'session_id':'s1','exercise':'squat','reps':3,
        'ended_at':1000,'status':'completed'});
    await tester.pumpAndSettle();
    expect(controller.summary?['exercise'], 'squat');
    expect(find.text('Current: Squat'), findsOneWidget);
    expect(find.text('3 complete cycles · target not assigned'), findsOneWidget);
    expect(find.text('Waiting for Pi exercise'), findsNothing);
    await tester.tap(find.text('Workout').last);
    await tester.pump();
    expect(find.textContaining('Session ended · 3 complete cycles'), findsOneWidget);
    expect(find.textContaining('Angle: —°'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());controller.dispose();
    unawaited(samples.close());unawaited(summaries.close());await tester.pump();
  });
  testWidgets('mobile fixture view and unmount cancel listener',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var cancelled = 0, stopped = 0;
    final stream = StreamController<Object?>(onCancel: () async {
      cancelled++;
    });
    final controller = WorkoutSessionController(
        source: (_) => stream.stream,
        now: () => DateTime.fromMillisecondsSinceEpoch(100000));
    await tester.pumpWidget(MaterialApp(
        home: HomeScreen(
            userName: 'Test',
            sessionId: 's1',
            demo: true,
            sessionController: controller,
            stopAudio: () async {
              stopped++;
            })));
    await tester.pump();
    stream.add(fixture(exercise: 'hanging_leg_raise'));
    await tester.pump();
    await tester.tap(find.text('Workout').last);
    await tester.pump();
    expect(find.text('Tracking · form not evaluated'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    expect(cancelled, 1);
    expect(stopped, 1);
    controller.dispose();
    unawaited(stream.close());
    await tester.pump();
  });
  testWidgets('workout unknown/lost/stale and real logout lifecycle',
      (tester) async {
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var cancellations = 0, signOuts = 0, audioStops = 0;
    var now = DateTime.fromMillisecondsSinceEpoch(100000);
    final stream = StreamController<Object?>(onCancel: () async {
      cancellations++;
    });
    final controller =
        WorkoutSessionController(source: (_) => stream.stream, now: () => now);
    await tester.pumpWidget(MaterialApp(
        home: HomeScreen(
            userName: 'Test',
            sessionId: 's1',
            demo: true,
            sessionController: controller,
            signOut: () async {
              signOuts++;
            },
            stopAudio: () async {
              audioStops++;
            })));
    await tester.pump();
    await tester.tap(find.text('Workout').last);
    await tester.pump();
    expect(find.text('Perfect Form - Keep Going!'), findsNothing);
    expect(
        find.text('Waiting for Pi data · form not evaluated'), findsOneWidget);
    stream.add(fixture());
    await tester.pump();
    expect(find.text('Tracking · form not evaluated'), findsOneWidget);
    stream.add(fixture(seq: 2, tracking: 'lost', angle: null));
    await tester.pump();
    expect(find.text('Cannot see required joints · counting paused'),
        findsOneWidget);
    expect(find.textContaining('Angle: —°'), findsOneWidget);
    now = now.add(const Duration(seconds: 3));
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.text('Stale data · no fresh sample for 2 seconds'),
        findsOneWidget);
    await tester.tap(find.text('Profile').last);
    await tester.pump();
    await tester.ensureVisible(find.text('LOG OUT'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('LOG OUT'));
    await tester.pumpAndSettle();
    expect(cancellations, 1);
    expect(audioStops, greaterThanOrEqualTo(1));
    expect(signOuts, 1);
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
    unawaited(stream.close());
    await tester.pump();
  });
}
