// Prototype schema-2 observer. The Pi owns exercise/rep state; no image stream.
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'local_demo_auth.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';
import 'main.dart';
import 'login_screen.dart';
import 'edit_profile_screen.dart';
import 'workout_session.dart';

class HomeScreen extends StatefulWidget {
  final String userName;
  final String sessionId;
  final bool demo;
  final bool autoSaveTiming;
  final WorkoutSessionController? sessionController;
  final Future<void> Function()? signOut;
  final Future<void> Function()? stopAudio;

  const HomeScreen({
    super.key,
    required this.userName,
    required this.sessionId,
    this.demo = false,
    this.autoSaveTiming = false,
    this.sessionController,
    this.signOut,
    this.stopAudio,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;

  // CÁC BIẾN LƯU THÔNG TIN NGƯỜI DÙNG
  late String userName;
  String userCondition = 'Post-Stroke Recovery';
  String userHeight = '165 cm';
  String userWeight = '60 kg';

  // 1. DANH SÁCH BÀI TẬP VÀ CÂU LỆNH GIỌNG NÓI CHUYÊN BIỆT
  final List<Map<String, dynamic>> exercises = exerciseNames.entries
      .map((e) => {
            'id': e.key,
            'name': e.value,
            'target': 'Complete cycles · selected on Pi',
            'targetReps': '—',
            'isDone': false,
            'jointName': e.key == 'squat'
                ? 'Knee internal angle (2D)'
                : e.key == 'hanging_leg_raise'
                    ? 'Hip internal angle (2D)'
                    : 'Elbow internal angle (2D)',
          })
      .toList();

  int currentExerciseIndex = 0;
  int repsCount = 0;
  double? currentAngle;
  String currentPhase = 'IDLE';
  bool isPostureError = false;

  // Biến chứa ảnh camera từ Raspberry Pi
  late final WorkoutSessionController _session;
  bool _loggingOut = false;
  bool _timingSaved = false;
  bool get _hasSessionData => _session.sample != null || _session.summary != null;

  final FlutterTts flutterTts = FlutterTts();

  @override
  void initState() {
    super.initState();
    if (widget.autoSaveTiming) _selectedIndex = 1;
    userName = widget.userName;
    _session = widget.sessionController ??
        WorkoutSessionController(
            foreground: () => WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed,
            source: widget.demo
                ? demoWorkoutSource
                : (id) => FirebaseDatabase.instance
                    .ref('$configuredSessionRoot/$id/latest')
                    .onValue
                    .map((event) => event.snapshot.value),
            summarySource: widget.demo ? null : (id) => FirebaseDatabase.instance
                .ref('$configuredSessionRoot/$id/summary').onValue.map((event) => event.snapshot.value),
            connectionSource: widget.demo ? null : FirebaseDatabase.instance
                .ref('.info/connected').onValue.map((event) => event.snapshot.value == true));
    _session.addListener(_onSession);
    unawaited(_session.bind(widget.sessionId));
    if (!widget.demo && widget.sessionController == null) {
      _loadUserProfile();
    }
  }

  Future<void> _stopAudio() async {
    if (widget.stopAudio != null) {
      await widget.stopAudio!();
    } else if (!widget.demo && widget.sessionController == null) {
      await flutterTts.stop();
    }
  }

  // TẢI DỮ LIỆU PROFILE THẬT TỪ FIREBASE
  Future<void> _loadUserProfile() async {
    try {
      final user = FirebaseAuth.instance.currentUser;
      if (user != null) {
        final ref = FirebaseDatabase.instance.ref('users/${user.uid}/profile');
        final snapshot = await ref.get();

        if (snapshot.exists) {
          final data = snapshot.value as Map<dynamic, dynamic>;
          if (mounted) {
            setState(() {
              userName = data['name'] ?? data['fullName'] ?? userName;
              userCondition = data['condition'] ?? userCondition;
              if (data['height'] != null) userHeight = '${data['height']} cm';
              if (data['weight'] != null) userWeight = '${data['weight']} kg';
            });
          }
        }
      }
    } catch (e) {
      debugPrint("Error loading profile: $e");
    }
  }

  void _onSession() {
    if (!mounted) return;
    setState(() {
      final sample = _session.sample;
      if (sample != null) {
        currentExerciseIndex =
            exercises.indexWhere((e) => e['id'] == sample.exercise);
        repsCount = sample.reps;
      }
      final summary = _session.summary;
      if (summary != null) {
        currentExerciseIndex = exercises.indexWhere((e) => e['id'] == summary['exercise']);
        repsCount = summary['reps'] as int;
      }
      currentAngle = _session.status == 'tracking' ? sample?.angle : null;
      currentPhase = _session.status == 'tracking'
          ? sample!.phase
          : _session.status.toUpperCase();
      isPostureError = false; // v2 does not evaluate posture correctness.
    });
    final sequence = _session.sample?.sequence;
    if (widget.autoSaveTiming && !_timingSaved && _session.summary != null && _session.timings.isNotEmpty) {
      _timingSaved = true;
      unawaited(saveLocalTiming(jsonEncode({'clock_verified':false,'rows':_session.timings}))
          .catchError((Object _) {_timingSaved = false;}));
    }
    if (sequence != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _session.recordRender(sequence);
      });
    }
  }

  String get _feedback => switch (_session.status) {
        'ended' => 'Session ended · $repsCount complete cycles · ${_session.summary?['status']}',
        'tracking' => 'Tracking · form not evaluated',
        'lost' => 'Cannot see required joints · counting paused',
        'selecting_side' => 'Selecting visible side · please wait',
        'stale' => 'Stale data · no fresh sample for 2 seconds',
        'error' => _session.error ?? 'Session error',
        _ => 'Waiting for Pi data · form not evaluated',
      };

  Future<void> _logout() async {
    if (_loggingOut) return;
    setState(() => _loggingOut = true);
    try {
      await _session.close();
    } catch (_) {/* A listener cleanup failure must not block sign-out. */}
    try {
      await _stopAudio();
    } catch (_) {/* Audio must not prevent sign-out. */}
    try {
      if (widget.signOut != null) {
        await widget.signOut!();
      } else if (Firebase.apps.isNotEmpty) {
        await FirebaseAuth.instance.signOut();
      }
      if (!mounted) return;
      Navigator.pushAndRemoveUntil(context,
          MaterialPageRoute(builder: (_) => const LoginScreen()), (_) => false);
    } catch (_) {
      if (mounted) {
        setState(() => _loggingOut = false);
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Sign out failed; please retry')));
      }
    }
  }

  @override
  void dispose() {
    _session.removeListener(_onSession);
    if (widget.sessionController == null) {
      _session.dispose();
    } else {
      unawaited(_session.close());
    }
    unawaited(_stopAudio().catchError((Object _) {}));
    super.dispose();
  }

  // Bắt đầu một bài tập
  void _startSpecificExercise(int index) {
    setState(() => _selectedIndex = 1);
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content:
            Text('Read-only prototype: choose/start the exercise on Pi.')));
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> screens = [
      _buildHomeView(),
      _buildWorkoutView(),
      _buildHistoryView(),
      _buildProfileView(),
    ];

    return Scaffold(
      appBar: AppBar(
          actions: [IconButton(tooltip:'Copy timing JSON',icon:const Icon(Icons.copy),onPressed:() async {
            if (const bool.fromEnvironment('REHAB_LOCAL_AUTH')) {
              try {
                await saveLocalTiming(jsonEncode({'clock_verified':false,'rows':_session.timings}));
                if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('Timing saved on Mac')));
              } catch (_) {
                if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('Timing save failed; keep this page open')));
              }
              return;
            }
            await Clipboard.setData(ClipboardData(text:jsonEncode({'clock_verified':false,'rows':_session.timings})));
            if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('Timing JSON copied · clock not verified')));
          })],
          title: Text(widget.demo
              ? 'DEMO FIXTURE · no Pi/cloud data'
              : 'Session: ${widget.sessionId}'),
          bottom: PreferredSize(
              preferredSize: const Size.fromHeight(44),
              child: Column(children: [
                const Text('Prototype · history/profile examples are demo data', style: TextStyle(fontSize: 11)),
                Text(widget.demo ? 'Fixture · not a camera measurement' :
                    '${const bool.fromEnvironment("REHAB_EMULATOR") ? "EMULATOR · dữ liệu thử · " : ""}Firebase: ${_session.connected == true ? "connected" : "disconnected/unknown"} · Source: ${_session.summary?["source"] ?? _session.sample?.sourceKind ?? "unknown"} · TTS on Pi',
                    style: const TextStyle(fontSize: 11)),
              ]))),
      body: screens[_selectedIndex],
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 10,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: BottomNavigationBar(
          currentIndex: _selectedIndex,
          onTap: (index) {
            setState(() {
              _selectedIndex = index;
            });
          },
          selectedItemColor: AppColors.primary,
          unselectedItemColor: AppColors.textGray,
          showUnselectedLabels: true,
          type: BottomNavigationBarType.fixed,
          backgroundColor: Colors.white,
          elevation: 0,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.home_rounded),
              label: 'Home',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.fitness_center_rounded),
              label: 'Workout',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.history_rounded),
              label: 'History',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.person_rounded),
              label: 'Profile',
            ),
          ],
        ),
      ),
    );
  }

  // 🏠 TAB 0: HOME VIEW
  Widget _buildHomeView() {
    final currentEx = exercises[currentExerciseIndex];
    const double progressPercent = 0; // No prescribed target in v2 telemetry.

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      const CircleAvatar(
                        radius: 24,
                        child: Icon(Icons.person_outline),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Welcome back',
                              style: TextStyle(
                                color: AppColors.textGray,
                                fontSize: 12,
                              ),
                            ),
                            Text(
                              '$userName! 👋',
                              style: const TextStyle(
                                color: AppColors.textDark,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.circle, color: AppColors.primary, size: 8),
                      SizedBox(width: 6),
                      Text(
                        widget.demo
                            ? 'DEMO FIXTURE'
                            : _session.status.toUpperCase(),
                        style: TextStyle(
                          color: AppColors.primary,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 25),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.03),
                    blurRadius: 15,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              !_hasSessionData
                                  ? 'Waiting for Pi exercise'
                                  : "Current: ${currentEx['name']}",
                              style: const TextStyle(
                                color: AppColors.textDark,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '$repsCount complete cycles · target not assigned',
                              style: const TextStyle(
                                color: AppColors.textGray,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 60,
                            height: 60,
                            child: CircularProgressIndicator(
                              value: progressPercent,
                              strokeWidth: 6,
                              backgroundColor: Colors.grey.shade100,
                              valueColor: const AlwaysStoppedAnimation<Color>(
                                AppColors.primary,
                              ),
                            ),
                          ),
                          Text(
                            '—',
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                              color: AppColors.textDark,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    height: 55,
                    child: ElevatedButton.icon(
                      onPressed: () =>
                          _startSpecificExercise(currentExerciseIndex),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      icon: const Icon(Icons.play_arrow, color: Colors.white),
                      label: const Text(
                        'OBSERVE PI SESSION',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF9C3),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFDE68A), width: 1),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const CircleAvatar(
                    radius: 20,
                    child: Icon(Icons.medical_services_outlined),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Demo guidance · not clinical feedback',
                          style: TextStyle(
                            color: Color(0xFF854D0E),
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Wait for READY before starting. Form is not evaluated. Squat and curl are under evaluation; the other three exercises are not accepted yet.',
                          style: TextStyle(
                            color: const Color(0xFF713F12).withOpacity(0.9),
                            fontSize: 13,
                            height: 1.4,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 25),
            const Wrap(
              spacing: 12,
              runSpacing: 6,
              children: [
                Text(
                  "Supported exercises",
                  style: TextStyle(
                    color: AppColors.textDark,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  'Selected on Pi',
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 15),
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: exercises.length,
              itemBuilder: (context, index) {
                final ex = exercises[index];
                final isSelected =
                    _hasSessionData && currentExerciseIndex == index;

                return GestureDetector(
                  onTap: () => _startSpecificExercise(index),
                  child: Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: isSelected
                            ? AppColors.primary
                            : Colors.grey.shade100,
                        width: isSelected ? 2 : 1,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.02),
                          blurRadius: 10,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 48,
                          height: 48,
                          decoration: BoxDecoration(
                            color: (isSelected
                                    ? AppColors.primary
                                    : const Color(0xFF3B82F6))
                                .withOpacity(0.12),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Icon(
                            ex['isDone']
                                ? Icons.check_circle_rounded
                                : Icons.play_circle_fill_rounded,
                            color: ex['isDone']
                                ? AppColors.primary
                                : const Color(0xFF3B82F6),
                            size: 26,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                ex['name'],
                                style: const TextStyle(
                                  color: AppColors.textDark,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                "${ex['target']} • ${ex['jointName']}",
                                style: const TextStyle(
                                  color: AppColors.textGray,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: (isSelected
                                    ? AppColors.primary
                                    : (ex['isDone']
                                        ? AppColors.primary
                                        : AppColors.textGray))
                                .withOpacity(0.12),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            isSelected ? 'Pi selection' : 'Supported',
                            style: TextStyle(
                              color: isSelected
                                  ? AppColors.primary
                                  : (ex['isDone']
                                      ? AppColors.primary
                                      : AppColors.textDark),
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 10),
          ],
        ),
      ),
    );
  }

  // 🏃‍♂️ TAB 1: WORKOUT VIEW
  Widget _buildWorkoutView() {
    final curEx = exercises[currentExerciseIndex];

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      !_hasSessionData
                          ? 'Waiting for Pi exercise'
                          : curEx['name'],
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textDark,
                      ),
                    ),
                    Text(
                      !_hasSessionData
                          ? 'Joint not selected'
                          : curEx['jointName'],
                      style: const TextStyle(
                        color: AppColors.textGray,
                        fontSize: 13,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<int>(
                      value:
                          !_hasSessionData ? null : currentExerciseIndex,
                      hint: const Text('Pi selection'),
                      isDense: true,
                      icon: const Icon(Icons.arrow_drop_down,
                          color: AppColors.primary),
                      items: List.generate(exercises.length, (i) {
                        return DropdownMenuItem(
                          value: i,
                          child: Text(
                            exercises[i]['name'],
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        );
                      }),
                      onChanged: null, // Pi owns the active exercise.
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 15),

            // KHUNG LIVE CAMERA CÓ HỖ TRỢ HIỂN THỊ BASE64 TỪ RASPBERRY PI
            Expanded(
              flex: 5,
              child: Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  color: const Color(0xFF0F172A),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: isPostureError
                        ? Colors.red
                        : AppColors.primary.withOpacity(0.4),
                    width: 2.5,
                  ),
                  // NẾU CÓ ẢNH THÌ HIỂN THỊ, NẾU KHÔNG CÓ THÌ BỎ TRỐNG NỀN
                  // v2 telemetry has no Base64 video; streaming is out of scope.
                ),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // NẾU CHƯA CÓ DỮ LIỆU ẢNH THÌ HIỆN ICON THAY THẾ
                    Icon(
                      Icons.accessibility_new_rounded,
                      color:
                          isPostureError ? Colors.redAccent : AppColors.primary,
                      size: 130,
                    ),
                    Positioned(
                      top: 15,
                      left: 15,
                      right: 15,
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.red.withOpacity(0.25),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.circle, color: Colors.red, size: 8),
                                SizedBox(width: 6),
                                Text(
                                  'VIDEO NOT CONNECTED',
                                  style: TextStyle(
                                    color: Colors.red,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Text(
                              'PROTOTYPE',
                              style: TextStyle(
                                color: AppColors.primary,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Positioned(
                      top: 50,
                      right: 15,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.6),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Column(
                          children: [
                            const Text(
                              'REPS',
                              style: TextStyle(
                                color: AppColors.textGray,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              '$repsCount',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 26,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              '/ ${curEx['targetReps']}',
                              style: const TextStyle(
                                color: AppColors.primary,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    Positioned(
                      bottom: 15,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.5),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          'Phase: $currentPhase | Angle: ${currentAngle?.toStringAsFixed(1) ?? "—"}°',
                          style: TextStyle(
                            color: isPostureError
                                ? Colors.redAccent
                                : AppColors.primary,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Banner phản hồi
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: isPostureError
                    ? const Color(0xFFFEF2F2)
                    : AppColors.primary,
                borderRadius: BorderRadius.circular(16),
                border: isPostureError
                    ? Border.all(color: Colors.red.shade200)
                    : null,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    isPostureError
                        ? Icons.warning_amber_rounded
                        : Icons.check_circle_rounded,
                    color: isPostureError ? Colors.red : Colors.white,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Flexible(
                      child: Text(
                    _feedback,
                    style: TextStyle(
                      color:
                          isPostureError ? Colors.red.shade700 : Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                  )),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 📊 TAB 2: HISTORY VIEW
  Widget _buildHistoryView() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Recovery History',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textDark,
                      ),
                    ),
                    Text(
                      'Posture accuracy (%) over the last 7 days',
                      style: TextStyle(color: AppColors.textGray, fontSize: 13),
                    ),
                  ],
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: const Row(
                    children: [
                      Text(
                        'This Week',
                        style: TextStyle(
                          color: AppColors.textDark,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Icon(Icons.keyboard_arrow_down,
                          color: AppColors.textGray, size: 16),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.02),
                    blurRadius: 15,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'POSTURE ACCURACY',
                            style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.8,
                            ),
                          ),
                          SizedBox(height: 4),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.baseline,
                            textBaseline: TextBaseline.alphabetic,
                            children: [
                              Text(
                                '82%',
                                style: TextStyle(
                                  fontSize: 28,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textDark,
                                ),
                              ),
                              SizedBox(width: 6),
                              Text(
                                'weekly average',
                                style: TextStyle(
                                  color: AppColors.textGray,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Row(
                          children: [
                            Icon(Icons.trending_up_rounded,
                                color: AppColors.primary, size: 14),
                            SizedBox(width: 4),
                            Text(
                              '+9%',
                              style: TextStyle(
                                color: AppColors.primary,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    height: 120,
                    child: CustomPaint(painter: LineChartPainter()),
                  ),
                  const SizedBox(height: 10),
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Mon',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                      Text('Tue',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                      Text('Wed',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                      Text('Thu',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                      Text('Fri',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                      Text('Sat',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                      Text('Sun',
                          style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold)),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Recent Sessions · DEMO DATA',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.textDark,
              ),
            ),
            const SizedBox(height: 10),
            Expanded(
              child: ListView(
                physics: const BouncingScrollPhysics(),
                children: [
                  _buildSessionRow('Today, 09:30 AM', 'Bicep Curl - 15 mins',
                      '95% accuracy', true),
                  _buildSessionRow('Yesterday, 03:00 PM', 'Squat - 12 mins',
                      '88% accuracy', true),
                  _buildSessionRow('Oct 18, 10:15 AM',
                      'Shoulder Raise - 20 mins', '52% accuracy', false),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 👤 TAB 3: PROFILE VIEW
  Widget _buildProfileView() {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Column(
                children: [
                  const CircleAvatar(
                    radius: 40,
                    child: Icon(Icons.person_outline, size: 40),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    userName,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textDark,
                    ),
                  ),
                  const Text(
                    '+84 091 234 5678',
                    style: TextStyle(color: AppColors.textGray, fontSize: 13),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () async {
                      final result = await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => EditProfileScreen(
                            currentName: userName,
                            currentCondition: userCondition,
                            currentHeight: userHeight,
                            currentWeight: userWeight,
                          ),
                        ),
                      );
                      if (result == true) {
                        _loadUserProfile();
                      }
                    },
                    style: OutlinedButton.styleFrom(
                      side:
                          const BorderSide(color: AppColors.primary, width: 1),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20)),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 8),
                    ),
                    icon: const Icon(Icons.edit_rounded,
                        color: AppColors.primary, size: 14),
                    label: const Text(
                      'Edit Profile',
                      style: TextStyle(
                        color: AppColors.primary,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 25),
            const Text(
              'MEDICAL SUMMARY',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: AppColors.textGray,
                letterSpacing: 0.8,
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.grey.shade100),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.02),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                children: [
                  Row(
                    children: [
                      Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          color: AppColors.primary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.favorite_rounded,
                            color: AppColors.primary, size: 20),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'CONDITION',
                            style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            userCondition,
                            style: const TextStyle(
                              color: AppColors.textDark,
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const Divider(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        children: [
                          const Text(
                            'HEIGHT',
                            style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            userHeight,
                            style: const TextStyle(
                              color: AppColors.textDark,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      Column(
                        children: [
                          const Text(
                            'WEIGHT',
                            style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            userWeight,
                            style: const TextStyle(
                              color: AppColors.textDark,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const Column(
                        children: [
                          Text(
                            'BMI INDEX',
                            style: TextStyle(
                              color: AppColors.textGray,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          SizedBox(height: 2),
                          Text(
                            '22.0',
                            style: TextStyle(
                              color: AppColors.primary,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 25),
            const Text(
              'IOT DEVICE SETTINGS',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: AppColors.textGray,
                letterSpacing: 0.8,
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.grey.shade100),
              ),
              child: Column(
                children: [
                  Row(
                    children: [
                      Container(
                        width: 64,
                        height: 48,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF1E293B), Color(0xFF0F172A)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                              color: AppColors.primary.withOpacity(0.3)),
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.primary.withOpacity(0.15),
                              blurRadius: 12,
                            ),
                          ],
                        ),
                        child: Stack(
                          children: [
                            Positioned(
                              top: 6,
                              left: 6,
                              child: Container(
                                width: 10,
                                height: 6,
                                decoration: BoxDecoration(
                                  color: AppColors.primary.withOpacity(0.8),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                              ),
                            ),
                            Positioned(
                              top: 6,
                              right: 6,
                              child: Container(
                                width: 4,
                                height: 4,
                                decoration: const BoxDecoration(
                                  color: Color(0xFF34D399),
                                  shape: BoxShape.circle,
                                ),
                              ),
                            ),
                            Positioned(
                              bottom: 6,
                              left: 6,
                              right: 6,
                              child: Container(
                                height: 2,
                                decoration: BoxDecoration(
                                  color: AppColors.primary.withOpacity(0.3),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 15),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Raspberry Pi 4',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: AppColors.textDark,
                                fontSize: 14,
                              ),
                            ),
                            Text(
                              'Device pairing: prototype only',
                              style: TextStyle(
                                  color: AppColors.textGray, fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Text(
                              'UNVERIFIED',
                              style: TextStyle(
                                color: AppColors.primary,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'PROTOTYPE',
                            style: TextStyle(
                              color: AppColors.primary,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const Divider(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 45,
                    child: ElevatedButton.icon(
                      onPressed: () {},
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFF1F5F9),
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: const Icon(Icons.refresh_rounded,
                          color: AppColors.primary, size: 18),
                      label: const Text(
                        'Re-sync Device (not implemented)',
                        style: TextStyle(
                          color: AppColors.textDark,
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 25),
            SizedBox(
              width: double.infinity,
              height: 55,
              child: OutlinedButton.icon(
                onPressed: _loggingOut ? null : _logout,
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: Color(0xFFFECACA), width: 1.5),
                  backgroundColor: const Color(0xFFFEF2F2),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
                icon: const Icon(Icons.logout_rounded, color: Colors.red),
                label: const Text(
                  'LOG OUT',
                  style:
                      TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildSessionRow(String time, String title, String acc, bool isOk) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                time,
                style: const TextStyle(color: AppColors.textGray, fontSize: 11),
              ),
              const SizedBox(height: 4),
              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: AppColors.textDark,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                acc,
                style: const TextStyle(
                  color: AppColors.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          Icon(
            isOk ? Icons.check_circle_rounded : Icons.cancel_rounded,
            color: isOk ? AppColors.primary : Colors.red,
            size: 24,
          ),
        ],
      ),
    );
  }
}

class LineChartPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;

    final path = Path()
      ..moveTo(0, size.height * 0.75)
      ..cubicTo(
        size.width * 0.2,
        size.height * 0.45,
        size.width * 0.2,
        size.height * 0.55,
        size.width * 0.35,
        size.height * 0.65,
      )
      ..cubicTo(
        size.width * 0.5,
        size.height * 0.75,
        size.width * 0.6,
        size.height * 0.25,
        size.width * 0.75,
        size.height * 0.35,
      )
      ..cubicTo(
        size.width * 0.85,
        size.height * 0.4,
        size.width * 0.9,
        size.height * 0.15,
        size.width,
        size.height * 0.2,
      );

    final shadowPaint = Paint()
      ..color = AppColors.primary.withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);

    canvas.drawPath(path, shadowPaint);
    canvas.drawPath(path, paint);

    final dotPaint = Paint()..color = AppColors.primary;
    final borderPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    canvas.drawCircle(
        Offset(size.width * 0.35, size.height * 0.65), 5, dotPaint);
    canvas.drawCircle(
        Offset(size.width * 0.35, size.height * 0.65), 5, borderPaint);

    canvas.drawCircle(
        Offset(size.width * 0.75, size.height * 0.35), 5, dotPaint);
    canvas.drawCircle(
        Offset(size.width * 0.75, size.height * 0.35), 5, borderPaint);

    canvas.drawCircle(Offset(size.width, size.height * 0.2), 6, dotPaint);
    canvas.drawCircle(Offset(size.width, size.height * 0.2), 6, borderPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
