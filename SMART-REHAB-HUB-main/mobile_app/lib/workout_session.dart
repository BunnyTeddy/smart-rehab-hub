import 'dart:async';
import 'package:flutter/foundation.dart';

const exerciseNames = <String, String>{
  'squat': 'Squat',
  'biceps_curl': 'Biceps Curl',
  'shoulder_press': 'Shoulder Press',
  'bent_over_row': 'Bent-over Row',
  'hanging_leg_raise': 'Hanging Leg Raise',
};
bool validSessionId(String id) =>
    RegExp(r'^[A-Za-z0-9_-]{1,100}$').hasMatch(id);

String get configuredSessionRoot {
  const root = String.fromEnvironment('REHAB_SESSION_ROOT', defaultValue: 'sessions');
  if (!['sessions', 'demo_e2e_v1/sessions'].contains(root)) {
    throw StateError('Unsupported session root');
  }
  return root;
}

class WorkoutSample {
  final String sessionId, exercise, phase, trackingStatus;
  final String? side;
  final int sequence, reps, timestamp;
  final double sampleTimestampMs;
  final double? angle;
  final int? frameReceivedEpochMs;
  final String? sourceKind;
  const WorkoutSample(
      {required this.sessionId,
      required this.exercise,
      required this.phase,
      required this.trackingStatus,
      required this.side,
      required this.sequence,
      required this.reps,
      required this.timestamp,
      required this.sampleTimestampMs,
      required this.angle, this.frameReceivedEpochMs, this.sourceKind});
  static WorkoutSample? parse(Object? value, String expectedSession) {
    if (value is! Map ||
        value['schema_version'] != 2 ||
        value['session_id'] != expectedSession ||
        !exerciseNames.containsKey(value['exercise']) ||
        value['form_status'] != 'not_evaluated') {
      return null;
    }
    final sequence = value['sequence'], reps = value['reps'];
    final timestamp = value['timestamp'],
        sampleTime = value['sample_timestamp_ms'];
    final angle = value['angle'],
        side = value['side'],
        tracking = value['tracking_status'];
    if (sequence is! int ||
        sequence < 1 ||
        reps is! int ||
        reps < 0 ||
        timestamp is! int ||
        timestamp < 0 ||
        sampleTime is! num ||
        !sampleTime.isFinite ||
        sampleTime < 0 ||
        !['tracking', 'lost', 'selecting_side'].contains(tracking) ||
        ![null, 'left', 'right'].contains(side) ||
        !['WAIT_START', 'READY', 'OUTBOUND', 'AT_TARGET', 'RETURNING']
            .contains(value['phase'])) {
      return null;
    }
    if (angle != null &&
        (angle is! num || !angle.isFinite || angle < 0 || angle > 180)) {
      return null;
    }
    if (tracking == 'tracking' && (angle == null || side == null)) return null;
    if (tracking != 'tracking' && angle != null) return null;
    final frameTime = value['frame_received_epoch_ms'];
    final kind = value['source'];
    if (frameTime != null && (frameTime is! int || frameTime < 0)) return null;
    if (kind != null && !['camera', 'replay'].contains(kind)) return null;
    return WorkoutSample(
        sessionId: expectedSession,
        exercise: value['exercise'],
        phase: value['phase'],
        trackingStatus: tracking,
        side: side,
        sequence: sequence,
        reps: reps,
        timestamp: timestamp,
        sampleTimestampMs: sampleTime.toDouble(),
        angle: (angle as num?)?.toDouble(), frameReceivedEpochMs: frameTime,
        sourceKind: kind);
  }
}

/// Subscription lifecycle independent of Firebase, injectable for offline tests.
class WorkoutSessionController extends ChangeNotifier {
  final DateTime Function() now;
  final bool? Function() foreground;
  final Stream<Object?> Function(String sessionId) source;
  final Stream<Object?> Function(String sessionId)? summarySource;
  final Stream<bool>? connectionSource;
  StreamSubscription<Object?>? _subscription;
  StreamSubscription<Object?>? _summarySubscription;
  StreamSubscription<bool>? _connectionSubscription;
  Timer? _timer;
  WorkoutSample? sample;
  DateTime? _receivedAt;
  String? sessionId, error;
  Map<String, Object?>? summary;
  bool? connected;
  final List<Map<String, Object?>> timings = [];
  void recordRender(int sequence) {
    if (timings.isNotEmpty && timings.last['sequence'] == sequence) {
      timings.last.putIfAbsent('render_callback_epoch_ms', () => now().millisecondsSinceEpoch);
      timings.last.putIfAbsent('browser_foreground_at_render', foreground);
    }
  }
  bool _disposed = false;
  int _generation = 0;
  WorkoutSessionController({required this.source, this.summarySource,
      this.connectionSource, DateTime Function()? now, bool? Function()? foreground})
      : now = now ?? DateTime.now, foreground = foreground ?? (() => null);
  bool get isStale {
    if (sample == null || _receivedAt == null) return false;
    final time = now();
    return time.difference(_receivedAt!).inMilliseconds >= 2000 ||
        time.millisecondsSinceEpoch - (sample!.frameReceivedEpochMs ?? sample!.timestamp) >= 2000;
  }

  String get status {
    if (error != null) return 'error';
    if (summary != null) return 'ended';
    if (sample == null) return 'waiting';
    if (isStale) return 'stale';
    return sample!.trackingStatus;
  }

  Future<void> bind(String id) async {
    if (!validSessionId(id)) throw ArgumentError('Invalid session ID');
    final generation = ++_generation;
    _timer?.cancel();
    await _subscription?.cancel();
    await _summarySubscription?.cancel();
    await _connectionSubscription?.cancel();
    if (_disposed || generation != _generation) return;
    sessionId = id;
    sample = null;
    summary = null;
    connected = null;
    timings.clear();
    error = null;
    _receivedAt = null;
    notifyListeners();
    _connectionSubscription = connectionSource?.listen((value) {
      if (_disposed || generation != _generation) return;
      connected = value;
      notifyListeners();
    });
    _summarySubscription = summarySource?.call(id).listen((value) {
      if (_disposed || generation != _generation || value == null) return;
      if (value is! Map || value['session_id'] != id ||
          !exerciseNames.containsKey(value['exercise']) ||
          value['reps'] is! int || value['reps'] < 0 ||
          value['ended_at'] is! int || value['status'] is! String ||
          (sample != null && (value['exercise'] != sample!.exercise || value['reps'] < sample!.reps))) {
        error = 'Invalid session summary';
      } else {
        summary = Map<String, Object?>.from(value);
      }
      notifyListeners();
    }, onError: (Object _) {
      if (_disposed || generation != _generation) return;
      error = 'Cannot read session summary'; notifyListeners();
    });
    _subscription = source(id).listen((value) {
      if (_disposed || generation != _generation) return;
      if (summary != null) return;
      if (value == null) {
        sample = null;
        _receivedAt = null;
        notifyListeners();
        return;
      }
      final next = WorkoutSample.parse(value, id);
      if (next == null) {
        error = 'Unsupported or invalid session data';
        notifyListeners();
        return;
      }
      final old = sample;
      if (old != null &&
          (next.sequence <= old.sequence ||
              next.sampleTimestampMs <= old.sampleTimestampMs)) {
        return;
      }
      if (old != null &&
          (next.exercise != old.exercise ||
              next.reps < old.reps ||
              (old.side != null && next.side != old.side))) {
        error = 'Session changed unexpectedly; bind a new session';
        notifyListeners();
        return;
      }
      if (next.timestamp > now().millisecondsSinceEpoch + 5000 ||
          (next.frameReceivedEpochMs ?? 0) > now().millisecondsSinceEpoch + 5000) {
        error = 'Device clock mismatch';
        notifyListeners();
        return;
      }
      sample = next;
      _receivedAt = now();
      timings.add({'session_id':id,'sequence':next.sequence,
        'frame_received_epoch_ms':next.frameReceivedEpochMs,'published_at_epoch_ms':next.timestamp,
        'browser_received_epoch_ms':_receivedAt!.millisecondsSinceEpoch,
        'browser_foreground_at_receive':foreground(),'clock_verified':false});
      if (timings.length > 10000) timings.removeAt(0);
      error = null;
      notifyListeners();
    }, onError: (Object e) {
      if (!_disposed && generation == _generation) {
        error = 'Cannot read session';
        notifyListeners();
      }
    });
    _timer = Timer.periodic(const Duration(milliseconds: 250), (_) {
      if (!_disposed) notifyListeners();
    });
  }

  Future<void> close() async {
    ++_generation;
    _timer?.cancel();
    _timer = null;
    final subscription = _subscription;
    _subscription = null;
    await subscription?.cancel();
    await _summarySubscription?.cancel();
    await _connectionSubscription?.cancel();
    _summarySubscription = null;
    _connectionSubscription = null;
    sample = null;
    summary = null;
    connected = null;
    sessionId = null;
    timings.clear();
    _receivedAt = null;
    error = null;
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    _timer?.cancel();
    unawaited(_subscription?.cancel());
    unawaited(_summarySubscription?.cancel());
    unawaited(_connectionSubscription?.cancel());
    timings.clear();
    super.dispose();
  }
}

/// Synthetic fixture, not Pi measurements. Never writes to cloud.
Stream<Object?> demoWorkoutSource(String id) async* {
  for (var i = 1;; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    final lost = i % 30 >= 24;
    yield <String, Object?>{
      'schema_version': 2,
      'session_id': id,
      'exercise': 'biceps_curl',
      'sequence': i,
      'sample_timestamp_ms': i * 200,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
      'angle': lost ? null : 160.0,
      'side': 'left',
      'reps': 0,
      'phase': lost ? 'WAIT_START' : 'READY',
      'tracking_status': lost ? 'lost' : 'tracking',
      'form_status': 'not_evaluated'
    };
  }
}
