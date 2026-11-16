import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/product/api.dart';
import 'package:mobile_app/product/contract.dart';
import 'package:mobile_app/product/exercise_setup.dart';

class PreviewApi extends Fake implements RehabApi {
  final Map<String, dynamic> state;
  Map<String, dynamic>? sent;
  @override
  Future<Map<String, dynamic>> command(String hub, String action,
      {String? exercise,
      int? duration,
      String? sessionId,
      String? requestedSide,
      Map<String, dynamic>? goal}) async {
    sent = {
      'exercise': exercise,
      'requested_side': requestedSide,
      'goal': goal
    };
    return {'status': 'accepted', 'session_id': 'test'};
  }

  PreviewApi(this.state);
  @override
  Stream<Map<String, dynamic>> watch(String path) => Stream.value(state);
  @override
  Stream<bool> get connection => Stream.value(true);
}

Map<String, dynamic> hubState({bool modern = true}) => {
      'state': 'idle',
      'ready': true,
      'updated_at': DateTime.now().millisecondsSinceEpoch,
      if (modern)
        'capabilities': {
          'protocol_version': 2,
          'exercises': {for (final e in exerciseLibrary) e['id']: true},
          'modes': {'time': true, 'sets': true},
          'bilateral': {
            for (final e in exerciseLibrary) e['id']: e['bilateral'] == true
          }
        }
    };
void main() {
  test('four active entries share names, guidance, pictures and side policy',
      () {
    expect(exerciseLibrary.map((e) => e['id']).toSet(),
        {'squat', 'biceps_curl', 'shoulder_flexion', 'shoulder_abduction'});
    expect(exerciseDetails('biceps_curl')['side_mode'], 'required');
    expect(exerciseDetails('squat')['side_mode'], 'auto');
    for (final e in exerciseLibrary) {
      expect(e['steps'], hasLength(3));
      expect(e['illustrations'], hasLength(3));
      expect(e['camera_text'], isNotEmpty);
      expect(e['visible_joints'], isNotEmpty);
    }
  });
  test('retired exercises stay readable in history but cannot start on any hub',
      () {
    final state = hubState();
    for (final e in retiredExercises) {
      final id = e['id'] as String;
      (state['capabilities']['exercises'] as Map)[id] = true;
      (state['capabilities']['bilateral'] as Map)[id] = true;
      expect(isExerciseAvailable(id), isFalse);
      expect(supportsExercise(state, id), isFalse);
      expect(supportsBoth(state, id), isFalse);
      expect(exerciseName(id), e['name']);
      expect(exerciseDetails(id)['angle_label'], isNotEmpty);
      expect(
          () => validateWorkoutGoal(
              id, 'left', {'mode': 'time', 'duration_s': 60}),
          throwsFormatException);
    }
  });
  test(
      'old hub permits only legacy exercises; modern validates anatomical side and bounded goals',
      () {
    expect(supportsExercise(hubState(modern: false), 'squat'), isTrue);
    expect(supportsExercise(hubState(modern: false), 'seated_hip_flexion'),
        isFalse);
    for (var i = 1; i <= 10; i++)
      validateWorkoutGoal(
          'squat', 'auto', {'mode': 'time', 'duration_s': i * 60});
    for (final reps in [5, 10, 15]) {
      for (final sets in [1, 2, 3]) {
        for (var rest = 15; rest <= 120; rest += 15) {
          validateWorkoutGoal('shoulder_flexion', 'left', {
            'mode': 'sets',
            'reps_per_set': reps,
            'sets': sets,
            'rest_s': rest
          });
        }
      }
    }
    expect(
        () => validateWorkoutGoal(
            'biceps_curl', 'auto', {'mode': 'time', 'duration_s': 60}),
        throwsFormatException);
    expect(
        () => validateWorkoutGoal(
            'squat', 'auto', {'mode': 'time', 'duration_s': 61}),
        throwsFormatException);
    expect(
        () => validateWorkoutGoal('squat', 'auto',
            {'mode': 'sets', 'reps_per_set': 5, 'sets': 3, 'rest_s': 31}),
        throwsFormatException);
  });
  testWidgets(
      'new setup fits narrow Android with large text and reveals rest only for multiple sets',
      (tester) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final state = hubState();
    await tester.pumpWidget(MaterialApp(
        builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(1.5)),
            child: child!),
        home: ExerciseSetupPage(
            api: PreviewApi(state),
            hubId: 'h1',
            exerciseId: 'biceps_curl',
            initialState: state)));
    await tester.pump();
    expect(find.text('Cách tập'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Theo lần và hiệp'), 300);
    await tester.ensureVisible(find.text('Theo lần và hiệp'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Theo lần và hiệp'));
    await tester.pump();
    expect(find.byKey(const ValueKey('rest-slider')), findsNothing);
    await tester.ensureVisible(find.text('3 hiệp'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('3 hiệp'));
    await tester.pump();
    expect(find.byKey(const ValueKey('rest-slider')), findsOneWidget);
    await tester.ensureVisible(find.text('Bắt đầu buổi tập'));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
  test(
      'both selection needs compatible hub and diagnostics identify the missing joint',
      () {
    expect(supportsBoth(hubState(), 'shoulder_flexion'), isTrue);
    final old = hubState();
    (old['capabilities'] as Map).remove('bilateral');
    expect(supportsBoth(old, 'shoulder_flexion'), isFalse);
    expect(supportsBoth(hubState(), 'standing_hip_abduction'), isFalse);
    validateWorkoutGoal(
        'shoulder_flexion', 'both', {'mode': 'time', 'duration_s': 180});
    expect(
        () => validateWorkoutGoal('standing_hip_abduction', 'both',
            {'mode': 'time', 'duration_s': 180}),
        throwsFormatException);
    expect(
        detectionHint(
            {'reason': 'left:landmark_15_out_of_frame'}, 'shoulder_flexion'),
        contains('cổ tay trái'));
    expect(detectionHint({'reason': 'hip_guard'}, 'seated_knee_extension'),
        contains('tư thế ngồi'));
    expect(sideText('both'), 'Cả hai cùng lúc');
    expect(
        detectionHint(
            {'workload_phase': 'aligning', 'phase': 'READY', 'reason': 'ok'},
            'shoulder_abduction'),
        contains('chờ đếm ngược'));
  });
  testWidgets('both option and dragged duration are submitted together',
      (tester) async {
    final state = hubState(), api = PreviewApi(hubState());
    await tester.pumpWidget(MaterialApp(
        home: ExerciseSetupPage(
            api: api,
            hubId: 'h1',
            exerciseId: 'shoulder_abduction',
            initialState: state)));
    await tester.pump();
    await tester.scrollUntilVisible(find.text('Cả hai cùng lúc'), 300);
    await tester.ensureVisible(find.text('Cả hai cùng lúc'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cả hai cùng lúc'));
    await tester.pump();
    final slider = find.byKey(const ValueKey('duration-slider'));
    await tester.scrollUntilVisible(slider, 200);
    await tester.ensureVisible(slider);
    await tester.pumpAndSettle();
    await tester.drag(slider, const Offset(100, 0));
    await tester.pumpAndSettle();
    final selected = tester.widget<Slider>(slider).value.round();
    expect(selected, greaterThan(3));
    expect(selected, lessThanOrEqualTo(10));
    await tester.scrollUntilVisible(find.text('Bắt đầu buổi tập'), 200);
    await tester.ensureVisible(find.text('Bắt đầu buổi tập'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Bắt đầu buổi tập'));
    await tester.pump();
    expect(api.sent?['requested_side'], 'both');
    expect(api.sent?['goal'], {'mode': 'time', 'duration_s': selected * 60});
    expect(tester.takeException(), isNull);
  });
  testWidgets('legacy hub setup has only 3,5,10 minute choices and no sets',
      (tester) async {
    final state = hubState(modern: false);
    await tester.pumpWidget(MaterialApp(
        home: ExerciseSetupPage(
            api: PreviewApi(state),
            hubId: 'h1',
            exerciseId: 'squat',
            initialState: state)));
    await tester.pump();
    expect(find.text('Theo lần và hiệp'), findsNothing);
    await tester.scrollUntilVisible(find.text('3 phút'), 300);
    expect(find.text('3 phút'), findsOneWidget);
    expect(find.text('5 phút'), findsOneWidget);
    expect(find.text('10 phút'), findsOneWidget);
    expect(find.text('1 phút'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
