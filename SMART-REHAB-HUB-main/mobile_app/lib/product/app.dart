import 'dart:async';
import 'dart:math' as math;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'api.dart';
import 'ble_setup.dart';
import 'contract.dart';
import 'exercise_setup.dart';

const ink = Color(0xff153e36);
const green = Color(0xff087f69);
String readableError(Object error) {
  if (error is FirebaseAuthException) {
    return const {
          'invalid-credential': 'Email hoặc mật khẩu chưa đúng.',
          'wrong-password': 'Email hoặc mật khẩu chưa đúng.',
          'user-not-found': 'Email hoặc mật khẩu chưa đúng.',
          'email-already-in-use': 'Email này đã được đăng ký.',
          'invalid-email': 'Email chưa hợp lệ.',
          'weak-password': 'Hãy dùng mật khẩu ít nhất 8 ký tự.',
          'network-request-failed': 'Chưa kết nối được Internet.',
          'too-many-requests': 'Bạn thử lại sau ít phút nhé.'
        }[error.code] ??
        'Chưa đăng nhập được. Kiểm tra kết nối và thử lại nhé.';
  }
  if (error is FirebaseException) {
    if (['permission-denied', 'permission_denied'].contains(error.code)) {
      return 'Chưa có quyền thực hiện yêu cầu với hub này. Bạn kiểm tra tài khoản đã ghép hub hoặc liên hệ nhóm hỗ trợ.';
    }
    if (['network-error', 'network_error', 'disconnected', 'unavailable']
        .contains(error.code)) {
      return 'Điện thoại chưa kết nối được máy chủ. Kiểm tra Internet và thử lại nhé.';
    }
    return 'Máy chủ chưa xử lý được yêu cầu. Bạn thử lại sau một chút nhé.';
  }
  if (error is StateError) return error.message;
  if (error is FormatException) return error.message;
  return 'Chưa tải được dữ liệu. Kiểm tra kết nối và thử lại nhé.';
}

void notice(BuildContext context, Object error) => ScaffoldMessenger.of(context)
    .showSnackBar(SnackBar(content: Text(readableError(error))));

class ProductApp extends StatelessWidget {
  const ProductApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'SMART REHAB',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
            useMaterial3: true,
            scaffoldBackgroundColor: const Color(0xfff3f7f5),
            colorScheme: ColorScheme.fromSeed(
                seedColor: green, primary: green, surface: Colors.white),
            appBarTheme: const AppBarTheme(
                backgroundColor: Color(0xfff3f7f5),
                foregroundColor: ink,
                centerTitle: false),
            inputDecorationTheme: InputDecorationTheme(
                filled: true,
                fillColor: const Color(0xfff3f7f5),
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: BorderSide.none)),
            filledButtonTheme: FilledButtonThemeData(
                style: FilledButton.styleFrom(
                    minimumSize: const Size(0, 54),
                    textStyle: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16))))),
        home: StreamBuilder<User?>(
            stream: FirebaseAuth.instance.authStateChanges(),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Scaffold(
                    body: Center(child: CircularProgressIndicator()));
              }
              return snapshot.data == null
                  ? const SignInPage()
                  : PatientShell(key: ValueKey(snapshot.data!.uid));
            }),
      );
}

class SignInPage extends StatefulWidget {
  const SignInPage({super.key});
  @override
  State<SignInPage> createState() => _SignInPageState();
}

class _SignInPageState extends State<SignInPage> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController(),
      password = TextEditingController(),
      name = TextEditingController();
  bool register = false, busy = false, hide = true;
  String? error;
  @override
  void dispose() {
    email.dispose();
    password.dispose();
    name.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!form.currentState!.validate()) return;
    final enteredName = name.text.trim();
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final api = RehabApi();
      if (register) {
        final result = await api.auth.createUserWithEmailAndPassword(
            email: email.text.trim(), password: password.text);
        await result.user!.updateDisplayName(enteredName);
        await api.saveProfile(enteredName);
      } else {
        await api.auth.signInWithEmailAndPassword(
            email: email.text.trim(), password: password.text);
      }
      await api.requirePatient();
    } catch (e) {
      if (mounted) setState(() => error = readableError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
          body: SafeArea(
              child: Center(
                  child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Icon(Icons.accessibility_new_rounded,
                  size: 50, color: green),
              const SizedBox(height: 20),
              const Text('SMART REHAB',
                  style: TextStyle(
                      color: green,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 2)),
              const SizedBox(height: 16),
              Text(
                  register
                      ? 'Bắt đầu hành trình\ntập luyện của bạn.'
                      : 'Chào bạn,\ncùng tập hôm nay nhé.',
                  style: const TextStyle(
                      fontSize: 32,
                      height: 1.2,
                      color: ink,
                      fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              const Text(
                  'Kết nối với hub tại nhà và theo dõi từng buổi tập cùng bác sĩ.',
                  style: TextStyle(
                      fontSize: 16, height: 1.5, color: Color(0xff5b7069))),
              const SizedBox(height: 28),
              Form(
                  key: form,
                  child: Column(children: [
                    if (register) ...[
                      TextFormField(
                          controller: name,
                          decoration:
                              const InputDecoration(labelText: 'Tên của bạn'),
                          textCapitalization: TextCapitalization.words,
                          validator: (v) => v == null ||
                                  v.trim().isEmpty ||
                                  v.trim().length > 100
                              ? 'Nhập tên từ 1 đến 100 ký tự.'
                              : null),
                      const SizedBox(height: 12)
                    ],
                    TextFormField(
                        controller: email,
                        decoration: const InputDecoration(labelText: 'Email'),
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        validator: (v) => v == null || !v.contains('@')
                            ? 'Nhập địa chỉ email của bạn.'
                            : null),
                    const SizedBox(height: 12),
                    TextFormField(
                        controller: password,
                        obscureText: hide,
                        autofillHints: [
                          register
                              ? AutofillHints.newPassword
                              : AutofillHints.password
                        ],
                        decoration: InputDecoration(
                            labelText: 'Mật khẩu',
                            suffixIcon: IconButton(
                                tooltip: hide ? 'Hiện mật khẩu' : 'Ẩn mật khẩu',
                                onPressed: () => setState(() => hide = !hide),
                                icon: Icon(hide
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined))),
                        validator: (v) => v == null ||
                                v.length < (register ? 8 : 1)
                            ? 'Nhập mật khẩu${register ? ' ít nhất 8 ký tự' : ''}.'
                            : null),
                    if (error != null)
                      Padding(
                          padding: const EdgeInsets.only(top: 16),
                          child: Text(error!,
                              style: TextStyle(
                                  color: Theme.of(context).colorScheme.error))),
                    const SizedBox(height: 22),
                    SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                            onPressed: busy ? null : submit,
                            child: Text(busy
                                ? 'Đang kết nối…'
                                : register
                                    ? 'Tạo tài khoản'
                                    : 'Đăng nhập'))),
                    TextButton(
                        onPressed: busy
                            ? null
                            : () => setState(() {
                                  register = !register;
                                  error = null;
                                }),
                        child: Text(register
                            ? 'Đã có tài khoản? Đăng nhập'
                            : 'Chưa có tài khoản? Đăng ký')),
                    if (!register)
                      TextButton(
                          onPressed: busy
                              ? null
                              : () async {
                                  if (!email.text.contains('@')) {
                                    setState(() => error =
                                        'Nhập email để nhận hướng dẫn đặt lại mật khẩu.');
                                    return;
                                  }
                                  try {
                                    await FirebaseAuth.instance
                                        .sendPasswordResetEmail(
                                            email: email.text.trim());
                                    if (mounted) {
                                      setState(() => error =
                                          'Nếu email đã đăng ký, bạn sẽ nhận được hướng dẫn đặt lại mật khẩu.');
                                    }
                                  } catch (e) {
                                    if (mounted) {
                                      setState(() => error = readableError(e));
                                    }
                                  }
                                },
                          child: const Text('Quên mật khẩu?')),
                  ])),
            ])),
      ))));
}

class PatientShell extends StatefulWidget {
  const PatientShell({super.key});
  @override
  State<PatientShell> createState() => _PatientShellState();
}

class _PatientShellState extends State<PatientShell> {
  final api = RehabApi();
  int tab = 0;
  late Future<void> role = api.requirePatient();
  @override
  Widget build(BuildContext context) => FutureBuilder<void>(
      future: role,
      builder: (context, roleState) {
        if (roleState.connectionState != ConnectionState.done) {
          return const Scaffold(
              body: Center(child: CircularProgressIndicator()));
        }
        if (roleState.hasError) {
          return Scaffold(
              body: Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(readableError(roleState.error!), textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(
                onPressed: () => setState(() => role = api.requirePatient()),
                child: const Text('Thử lại')),
            TextButton(
                onPressed: () => api.auth.signOut(),
                child: const Text('Đăng xuất')),
          ])));
        }
        return Scaffold(
            appBar: AppBar(
                title: const Text('SMART REHAB',
                    style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 20,
                        letterSpacing: 1))),
            body: SafeArea(
                child: IndexedStack(index: tab, children: [
              HomePage(api: api),
              HistoryPage(api: api),
              AccountPage(api: api)
            ])),
            bottomNavigationBar: NavigationBar(
                selectedIndex: tab,
                onDestinationSelected: (i) => setState(() => tab = i),
                destinations: const [
                  NavigationDestination(
                      icon: Icon(Icons.home_outlined),
                      selectedIcon: Icon(Icons.home),
                      label: 'Tập luyện'),
                  NavigationDestination(
                      icon: Icon(Icons.history), label: 'Lịch sử'),
                  NavigationDestination(
                      icon: Icon(Icons.person_outline), label: 'Cá nhân'),
                ]));
      });
}

class DbView extends StatefulWidget {
  final RehabApi api;
  final String path;
  final Widget Function(Map<String, dynamic>) builder;
  const DbView(
      {super.key,
      required this.api,
      required this.path,
      required this.builder});
  @override
  State<DbView> createState() => _DbViewState();
}

class _DbViewState extends State<DbView> {
  late Stream<Map<String, dynamic>> stream;
  @override
  void initState() {
    super.initState();
    stream = widget.api.watch(widget.path);
  }

  @override
  void didUpdateWidget(DbView old) {
    super.didUpdateWidget(old);
    if (old.path != widget.path) stream = widget.api.watch(widget.path);
  }

  @override
  Widget build(BuildContext context) => StreamBuilder<Map<String, dynamic>>(
      stream: stream,
      builder: (context, s) {
        if (s.hasError) {
          return const InfoBox(
              'Chưa tải được dữ liệu hoặc quyền truy cập đã thay đổi.');
        }
        if (!s.hasData) {
          return const Padding(
              padding: EdgeInsets.all(30),
              child: Center(child: CircularProgressIndicator()));
        }
        return widget.builder(s.data!);
      });
}

class InfoBox extends StatelessWidget {
  final String text;
  const InfoBox(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: const Color(0xffe3eee9),
          borderRadius: BorderRadius.circular(16)),
      child: Text(text, style: const TextStyle(height: 1.5, color: ink)));
}

class Panel extends StatelessWidget {
  final Widget child;
  const Panel({super.key, required this.child});
  @override
  Widget build(BuildContext context) => Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: const Color(0xffdfebe5))),
      child: child);
}

class HomePage extends StatefulWidget {
  final RehabApi api;
  const HomePage({super.key, required this.api});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late final stream = widget.api.hubId;
  @override
  Widget build(BuildContext context) =>
      ListView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 24), children: [
        DbView(
            api: widget.api,
            path: 'patients/${widget.api.uid}/profile',
            builder: (p) => Padding(
                padding: const EdgeInsets.only(bottom: 24),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Chào ${p['name'] ?? 'bạn'},',
                          style: const TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w700,
                              color: ink)),
                      const SizedBox(height: 8),
                      const Text('Từng buổi tập, từng bước tiến.',
                          style: TextStyle(
                              color: Color(0xff5b7069), fontSize: 16)),
                    ]))),
        StreamBuilder<String?>(
            stream: stream,
            builder: (context, s) {
              if (s.hasError) {
                return const InfoBox(
                    'Chưa tải được thông tin hub. Kiểm tra kết nối Internet.');
              }
              if (s.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (s.data == null) {
                return Panel(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      const Icon(Icons.connected_tv, color: green, size: 42),
                      const SizedBox(height: 18),
                      const Text('Kết nối hub của bạn',
                          style: TextStyle(
                              fontSize: 23,
                              fontWeight: FontWeight.w700,
                              color: ink)),
                      const SizedBox(height: 10),
                      const Text(
                          'Cắm nguồn hub, webcam và dây HDMI vào TV. Sau đó quét mã QR ghép hub do nhóm triển khai cung cấp hoặc dán trên vỏ để cài Wi-Fi.',
                          style: TextStyle(height: 1.5)),
                      const SizedBox(height: 22),
                      FilledButton.icon(
                          onPressed: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const WifiPage())),
                          icon: const Icon(Icons.qr_code_scanner),
                          label: const Text('Ghép hub')),
                    ]));
              }
              return HubCard(
                  key: ValueKey(s.data), api: widget.api, hubId: s.data!);
            }),
      ]);
}

class HubCard extends StatefulWidget {
  final RehabApi api;
  final String hubId;
  const HubCard({super.key, required this.api, required this.hubId});
  @override
  State<HubCard> createState() => _HubCardState();
}

class _HubCardState extends State<HubCard> {
  bool busy = false, connected = false;
  String? lastSession;
  Map<String, dynamic> state = {};
  late final StreamSubscription connection, hub;
  late final Timer timer;
  @override
  void initState() {
    super.initState();
    connection = widget.api.connection.listen((v) {
      if (mounted) setState(() => connected = v);
    });
    hub = widget.api.watch('hubState/${widget.hubId}').listen((v) {
      if (mounted) {
        setState(() {
          if (v['session_id'] is String) lastSession = v['session_id'];
          state = v;
        });
      }
    }, onError: (_) {
      if (mounted) setState(() => state = {});
    });
    timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    connection.cancel();
    hub.cancel();
    timer.cancel();
    super.dispose();
  }

  Future<void> command(String action) async {
    setState(() => busy = true);
    try {
      await widget.api
          .command(widget.hubId, action, sessionId: state['session_id']);
    } catch (e) {
      if (mounted) notice(context, e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final online = connected &&
        DateTime.now().millisecondsSinceEpoch - number(state['updated_at']) <
            8000;
    final active = state['session_id'] is String &&
        ['preparing', 'aligning', 'running', 'stopping']
            .contains(state['state']);
    return Column(children: [
      Panel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(online ? Icons.wifi : Icons.wifi_off,
              color: online ? green : Colors.deepOrange),
          const SizedBox(width: 10),
          Expanded(
              child: Text(
                  !connected
                      ? 'Điện thoại mất mạng'
                      : online
                          ? 'Hub đã kết nối'
                          : 'Hub chưa trực tuyến',
                  style: const TextStyle(
                      fontWeight: FontWeight.w700, fontSize: 17)))
        ]),
        const SizedBox(height: 6),
        Text('Hub ${widget.hubId}',
            style: const TextStyle(color: Color(0xff5b7069), fontSize: 12)),
        if (!connected && active)
          const InfoBox(
              'Nếu hub vẫn có Internet, buổi tập tiếp tục đến hết thời lượng. Mở lại app khi có mạng để kiểm tra.'),
        if (active) ...[
          const SizedBox(height: 20),
          Text(exerciseName(state['exercise']),
              style: const TextStyle(
                  fontSize: 26, fontWeight: FontWeight.bold, color: ink)),
          DbView(
              api: widget.api,
              path: 'sessions/${state['session_id']}/latest',
              builder: (v) {
                final fresh = online &&
                    DateTime.now().millisecondsSinceEpoch -
                            number(v['timestamp']) <
                        2500;
                final status = !online
                    ? 'Đang chờ kết nối lại'
                    : state['state'] == 'preparing'
                        ? 'Đang chuẩn bị webcam…'
                        : state['state'] == 'stopping'
                            ? 'Đang dừng buổi tập…'
                            : !fresh
                                ? 'Đang chờ dữ liệu mới'
                                : v['workload_phase'] == 'resting'
                                    ? 'Đang nghỉ giữa hiệp'
                                    : v['workload_phase'] == 'aligning'
                                        ? 'Căn người để sẵn sàng'
                                        : v['tracking_status'] != 'tracking'
                                            ? 'Chưa thấy đủ khớp'
                                            : state['state'] == 'running'
                                                ? 'Đang tập'
                                                : 'Căn người để sẵn sàng';
                return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 10),
                      Text(status,
                          style: const TextStyle(
                              color: green,
                              fontSize: 17,
                              fontWeight: FontWeight.w600)),
                      if (state['state'] != 'running' ||
                          v['tracking_status'] != 'tracking')
                        InfoBox(
                            exerciseDetails(state['exercise'])['camera_text'] ??
                                'Căn người trước webcam.'),
                      if (fresh &&
                          state['state'] != 'preparing' &&
                          state['state'] != 'stopping' &&
                          v['workload_phase'] != 'resting')
                        InfoBox(detectionHint(
                            v, state['exercise']?.toString() ?? '')),
                      if (fresh && v['goal'] != null) ...[
                        const SizedBox(height: 12),
                        Text(sideText(v['requested_side']),
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                        Text(goalText(v['goal'])),
                        if (asMap(v['goal'])['mode'] == 'sets')
                          Text(
                              'Hiệp ${number(v['set_number']).toInt()}/${number(asMap(v['goal'])['sets']).toInt()} · ${number(v['rep_in_set']).toInt()}/${number(asMap(v['goal'])['reps_per_set']).toInt()} lần',
                              style: const TextStyle(
                                  fontSize: 22, fontWeight: FontWeight.w700)),
                        Text(v['workload_phase'] == 'resting'
                            ? 'Nghỉ còn ${durationText(v['rest_remaining_s'])}'
                            : asMap(v['goal'])['mode'] == 'time'
                                ? 'Còn ${durationText(v['remaining_s'])}'
                                : phaseText(v['workload_phase'])),
                      ],
                      Padding(
                          padding: const EdgeInsets.symmetric(vertical: 24),
                          child: Row(children: [
                            Expanded(
                                child: Metric('${number(v['reps']).toInt()}',
                                    'lần đã hoàn thành')),
                            if (v['requested_side'] != 'both')
                              Expanded(
                                  child: Metric(
                                      fresh &&
                                              (v['angle'] is num ||
                                                  v['raw_angle'] is num)
                                          ? '${number(v['angle'] ?? v['raw_angle']).round()}°'
                                          : '—',
                                      exerciseDetails(state['exercise'])[
                                              'angle_label'] ??
                                          'Góc 2D')),
                          ])),
                      if (v['requested_side'] == 'both')
                        Row(children: [
                          Expanded(
                              child: Metric(
                                  fresh && v['angle_left'] is num
                                      ? '${number(v['angle_left']).round()}°'
                                      : '—',
                                  'Góc bên trái')),
                          Expanded(
                              child: Metric(
                                  fresh && v['angle_right'] is num
                                      ? '${number(v['angle_right']).round()}°'
                                      : '—',
                                  'Góc bên phải')),
                        ]),
                      const Text(
                          'Bạn có thể khóa màn hình. Hub tự quản lý thời gian, số lần và nghỉ giữa hiệp.',
                          style:
                              TextStyle(height: 1.4, color: Color(0xff5b7069))),
                    ]);
              }),
          const SizedBox(height: 20),
          SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xffa4362e)),
                  onPressed: busy || !online || state['state'] == 'stopping'
                      ? null
                      : () => command('stop'),
                  icon: const Icon(Icons.stop_rounded),
                  label: Text(busy ? 'Chờ hub xác nhận…' : 'Dừng buổi tập'))),
        ] else ...[
          if (online && state['display_ready'] != true)
            const InfoBox(
                'Bật TV và kiểm tra dây HDMI để thấy hình webcam khi tập.'),
          if (online && state['audio_ready'] != true)
            const InfoBox(
                'Bộ hướng dẫn âm thanh của hub chưa sẵn sàng. Cần hoàn tất cài đặt trước khi tập.'),
          const SizedBox(height: 24),
          const Text('Hôm nay bạn muốn tập bài nào?',
              style: TextStyle(
                  fontSize: 21, color: ink, fontWeight: FontWeight.w700)),
          const SizedBox(height: 16),
          if (!supportsProtocol2(state))
            const InfoBox(
                'Hub hiện hỗ trợ Squat và Gập tay trong 3, 5 hoặc 10 phút. Cập nhật hub để mở thêm bài và chế độ theo hiệp.'),
          for (final group
              in exerciseLibrary.map((e) => e['group'] as String).toSet()) ...[
            Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(group,
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.w700))),
            for (final e in exerciseLibrary.where((e) => e['group'] == group))
              Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: OutlinedButton(
                    onPressed: busy || !supportsExercise(state, e['id'])
                        ? null
                        : () => Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => ExerciseSetupPage(
                                    api: widget.api,
                                    hubId: widget.hubId,
                                    exerciseId: e['id'],
                                    initialState: state))),
                    style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.all(18),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16))),
                    child: Row(children: [
                      Icon(group == 'Tay–vai'
                          ? Icons.fitness_center
                          : Icons.accessibility_new),
                      const SizedBox(width: 12),
                      Expanded(
                          child: Text(e['name'],
                              style: const TextStyle(fontSize: 18))),
                      Icon(supportsExercise(state, e['id'])
                          ? Icons.chevron_right
                          : Icons.lock_outline)
                    ]),
                  )),
          ],
          if (lastSession != null)
            TextButton(
                onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) =>
                            SessionPage(api: widget.api, id: lastSession!))),
                child: const Text('Xem kết quả buổi vừa tập')),
          TextButton.icon(
              onPressed: busy
                  ? null
                  : () => Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (_) => WifiPage(hubId: widget.hubId))),
              icon: const Icon(Icons.wifi),
              label: const Text('Đổi mạng Wi-Fi')),
        ],
      ])),
    ]);
  }
}

class Metric extends StatelessWidget {
  final String value, label;
  const Metric(this.value, this.label, {super.key});
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value,
            style: const TextStyle(
                fontSize: 32, fontWeight: FontWeight.w700, color: ink)),
        Text(label,
            style: const TextStyle(color: Color(0xff5b7069), fontSize: 13))
      ]);
}

class QrPage extends StatefulWidget {
  final String type;
  const QrPage({super.key, required this.type});
  @override
  State<QrPage> createState() => _QrPageState();
}

class _QrPageState extends State<QrPage> {
  final controller = MobileScannerController();
  bool complete = false;
  String? error;
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
          title: Text(
              widget.type == 'hub' ? 'Quét mã trên vỏ hub' : 'Quét mã bác sĩ')),
      body: Column(children: [
        Expanded(
            child: MobileScanner(
                controller: controller,
                onDetect: (capture) {
                  if (complete) return;
                  final raw = capture.barcodes.firstOrNull?.rawValue;
                  if (raw == null) return;
                  try {
                    final qr = SetupQr.parse(raw, widget.type);
                    complete = true;
                    Navigator.pop(context, qr);
                  } catch (_) {
                    setState(() => error =
                        'Mã này chưa đúng. Hãy quét mã ${widget.type == 'hub' ? 'trên vỏ hub' : 'liên kết của bác sĩ'}.');
                  }
                },
                errorBuilder: (context, error) => const Center(
                    child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                            'Cần cho phép Camera để quét mã QR. Bạn có thể bật quyền trong Cài đặt của điện thoại.'))))),
        Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
                error ?? 'Đưa mã QR vào khung hình. Mã sẽ được đọc tự động.',
                textAlign: TextAlign.center)),
      ]));
}

class WifiPage extends StatefulWidget {
  final String? hubId;
  const WifiPage({super.key, this.hubId});
  @override
  State<WifiPage> createState() => _WifiPageState();
}

class _WifiPageState extends State<WifiPage> {
  final setup = BleSetup(),
      ssid = TextEditingController(),
      password = TextEditingController();
  SetupQr? qr;
  bool busy = false, done = false;
  String status = '';
  @override
  void initState() {
    super.initState();
    if (widget.hubId != null) {
      setup.savedQr(widget.hubId!).then((v) {
        if (mounted) setState(() => qr = v);
      });
    }
  }

  @override
  void dispose() {
    ssid.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
      canPop: !busy,
      child: Scaffold(
          appBar: AppBar(
              title: Text(widget.hubId == null ? 'Ghép hub' : 'Đổi Wi-Fi')),
          body: ListView(padding: const EdgeInsets.all(24), children: [
            const Icon(Icons.router_outlined, size: 64, color: green),
            const SizedBox(height: 24),
            const Text('Cài một lần, dùng mỗi ngày',
                style: TextStyle(
                    fontSize: 26, color: ink, fontWeight: FontWeight.w700)),
            const InfoBox(
                'Giữ hub bật và đặt điện thoại ở gần. Hub dùng mạng Wi-Fi có Internet; chọn mạng 2,4 GHz nếu tín hiệu ổn định hơn.'),
            OutlinedButton.icon(
                onPressed: busy || done
                    ? null
                    : () async {
                        final result = await Navigator.push<SetupQr>(
                            context,
                            MaterialPageRoute(
                                builder: (_) => const QrPage(type: 'hub')));
                        if (result != null && context.mounted) {
                          if (widget.hubId != null &&
                              result.id != widget.hubId) {
                            notice(context,
                                StateError('Hãy quét mã của hub đã ghép.'));
                            return;
                          }
                          setState(() => qr = result);
                        }
                      },
                icon: const Icon(Icons.qr_code_scanner),
                label: Text(qr == null
                    ? 'Quét mã trên vỏ hub'
                    : 'Đã chọn hub ${qr!.id}')),
            const SizedBox(height: 20),
            TextField(
                controller: ssid,
                enabled: !busy && !done,
                decoration: const InputDecoration(labelText: 'Tên mạng Wi-Fi'),
                autocorrect: false),
            const SizedBox(height: 12),
            TextField(
                controller: password,
                enabled: !busy && !done,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Mật khẩu Wi-Fi'),
                autocorrect: false),
            const SizedBox(height: 24),
            if (status.isNotEmpty) InfoBox(status),
            if (busy) const LinearProgressIndicator(),
            const SizedBox(height: 12),
            FilledButton(
                onPressed: busy || qr == null
                    ? null
                    : done
                        ? () => Navigator.pop(context)
                        : () async {
                            setState(() {
                              busy = true;
                              status = '';
                            });
                            try {
                              await setup.configure(
                                  qr!, ssid.text, password.text, (v) {
                                if (mounted) setState(() => status = v);
                              });
                              if (mounted) setState(() => done = true);
                            } catch (e) {
                              if (mounted) {
                                setState(() => status = readableError(e));
                              }
                            } finally {
                              if (mounted) setState(() => busy = false);
                            }
                          },
                child: Text(done
                    ? 'Về màn hình tập luyện'
                    : busy
                        ? 'Đang cài đặt…'
                        : 'Kết nối hub')),
          ])));
}

class HistoryPage extends StatefulWidget {
  final RehabApi api;
  const HistoryPage({super.key, required this.api});
  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  late final stream = widget.api.history;
  @override
  Widget build(BuildContext context) =>
      StreamBuilder<List<Map<String, dynamic>>>(
          stream: stream,
          builder: (context, s) {
            if (s.hasError) {
              return const Padding(
                  padding: EdgeInsets.all(24),
                  child: InfoBox(
                      'Chưa tải được lịch sử. Kiểm tra kết nối và thử lại.'));
            }
            if (!s.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            final rows = s.data!;
            return ListView(padding: const EdgeInsets.all(20), children: [
              const Text('Những buổi tập của bạn',
                  style: TextStyle(
                      fontSize: 26, fontWeight: FontWeight.w700, color: ink)),
              const SizedBox(height: 8),
              const Text('100 buổi gần nhất · Kết quả được lưu từ hub',
                  style: TextStyle(color: Color(0xff5b7069))),
              const SizedBox(height: 24),
              if (rows.isEmpty)
                const InfoBox(
                    'Bạn chưa có buổi tập nào. Kết quả đầu tiên sẽ xuất hiện ở đây sau khi bạn bắt đầu với hub.'),
              ...rows.map((row) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Material(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(18),
                      child: ListTile(
                        contentPadding: const EdgeInsets.all(16),
                        leading: const CircleAvatar(
                            backgroundColor: Color(0xffe3eee9),
                            child: Icon(Icons.fitness_center, color: green)),
                        title: Text(exerciseName(row['exercise']),
                            style:
                                const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Text(
                            '${dateText(row['created_at'])}\n${row['ended_at'] != null ? '${number(row['reps']).toInt()} lần · ${durationText(row['elapsed_s'])}' : 'Chưa có tổng kết'}',
                            style: const TextStyle(height: 1.6)),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => SessionPage(
                                    api: widget.api, id: row['session_id']))),
                      )))),
            ]);
          });
}

class SessionPage extends StatelessWidget {
  final RehabApi api;
  final String id;
  const SessionPage({super.key, required this.api, required this.id});
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('Kết quả buổi tập')),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        DbView(
            api: api,
            path: 'sessions/$id',
            builder: (s) {
              final meta = asMap(s['meta']), summary = asMap(s['summary']);
              final points = asMap(s['points']).values.map(asMap).toList()
                ..sort(
                    (a, b) => number(a['t_ms']).compareTo(number(b['t_ms'])));
              return Column(children: [
                Panel(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(exerciseName(meta['exercise']),
                          style: const TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w700,
                              color: ink)),
                      const SizedBox(height: 8),
                      Text(dateText(meta['created_at'])),
                      const SizedBox(height: 24),
                      if (summary.isEmpty)
                        const InfoBox(
                            'Buổi tập chưa có tổng kết. Nếu hub vừa mất mạng, kết quả sẽ cập nhật khi hub kết nối lại.')
                      else ...[
                        Row(children: [
                          Expanded(
                              child: Metric(
                                  '${number(summary['reps']).toInt()}',
                                  'lần hoàn thành')),
                          Expanded(
                              child: Metric(
                                  durationText(summary['active_s'] ??
                                      summary['elapsed_s']),
                                  'thời gian tập'))
                        ]),
                        const SizedBox(height: 18),
                        InfoBox(reasonText(summary['error'])),
                        if (summary['goal'] != null) ...[
                          Text('Mục tiêu: ${goalText(summary['goal'])}'),
                          Text(sideText(summary['requested_side'])),
                          if (asMap(summary['goal'])['mode'] == 'sets') ...[
                            Text(
                                'Hoàn thành ${number(summary['completed_sets']).toInt()}/${number(asMap(summary['goal'])['sets']).toInt()} hiệp'),
                            for (final set in asMap(summary['set_results'])
                                .values
                                .map(asMap))
                              Text(
                                  'Hiệp ${number(set['set_number']).toInt()}: ${number(set['reps']).toInt()}/${number(asMap(summary['goal'])['reps_per_set']).toInt()} lần · ${set['completed'] == true ? 'Đủ mục tiêu' : 'Chưa đủ'}'),
                            Text(
                                'Nghỉ: ${durationText(summary['rest_s'])} · Căn lại: ${durationText(summary['aligning_s'])}'),
                          ],
                        ],
                        Text(
                            'Nhận rõ khớp: ${durationText(summary['tracking_s'])}'),
                      ],
                    ])),
                if (points.isNotEmpty)
                  Panel(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(
                            exerciseDetails(meta['exercise'])['angle_label'] ??
                                'Góc khớp trong buổi tập',
                            style: const TextStyle(
                                fontSize: 19,
                                fontWeight: FontWeight.w700,
                                color: ink)),
                        const SizedBox(height: 8),
                        const Text(
                            'Góc 2D · 0–180° · Đoạn đứt: nghỉ hoặc thiếu dữ liệu',
                            style: TextStyle(color: Color(0xff5b7069))),
                        if (meta['requested_side'] == 'both')
                          const Text('Xanh: bên trái · Tím: bên phải'),
                        const SizedBox(height: 20),
                        SizedBox(
                            height: 160,
                            width: double.infinity,
                            child: CustomPaint(
                                painter: AnglePainter(points,
                                    both: meta['requested_side'] == 'both'))),
                      ])),
              ]);
            }),
        Panel(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Nhận xét của bác sĩ',
              style: TextStyle(
                  fontSize: 21, color: ink, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          DbView(
              api: api,
              path: 'comments/$id',
              builder: (rows) => rows.isEmpty
                  ? const Text('Chưa có nhận xét cho buổi tập này.',
                      style: TextStyle(color: Color(0xff5b7069)))
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: rows.values.map((v) {
                        final c = asMap(v);
                        return Padding(
                            padding: const EdgeInsets.only(bottom: 18),
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(c['doctor_name'] ?? 'Bác sĩ',
                                      style: const TextStyle(
                                          fontWeight: FontWeight.w700)),
                                  Text(dateText(c['updated_at']),
                                      style: const TextStyle(
                                          color: Color(0xff5b7069),
                                          fontSize: 12)),
                                  const SizedBox(height: 8),
                                  Text(c['text'] ?? '',
                                      style: const TextStyle(height: 1.5)),
                                ]));
                      }).toList())),
        ])),
      ]));
}

class AnglePainter extends CustomPainter {
  final List<Map<String, dynamic>> points;
  final bool both;
  AnglePainter(this.points, {this.both = false});
  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = const Color(0xffe3eee9)
      ..strokeWidth = 1;
    for (final y in [0.0, .5, 1.0]) {
      canvas.drawLine(Offset(0, y * size.height),
          Offset(size.width, y * size.height), grid);
    }
    if (points.isEmpty) return;
    final maxTime = math.max(1, number(points.last['t_ms']).toDouble());
    final series = both
        ? {'angle_left': green, 'angle_right': const Color(0xff8c55a8)}
        : {'angle': green};
    for (final entry in series.entries) {
      final path = Path();
      bool open = false;
      double? last;
      for (final p in points) {
        final time = number(p['t_ms']).toDouble(), angle = p[entry.key];
        if (angle is! num ||
            p['tracking_status'] != 'tracking' ||
            ['resting', 'aligning'].contains(p['workload_phase'])) {
          open = false;
          last = time;
          continue;
        }
        final x = time / maxTime * size.width,
            y = (1 - angle / 180) * size.height;
        if (!open || (last != null && time - last > 1500)) {
          path.moveTo(x, y);
        } else {
          path.lineTo(x, y);
        }
        open = true;
        last = time;
      }
      canvas.drawPath(
          path,
          Paint()
            ..color = entry.value
            ..strokeWidth = 2.5
            ..style = PaintingStyle.stroke);
    }
  }

  @override
  bool shouldRepaint(AnglePainter old) =>
      old.points != points || old.both != both;
}

class AccountPage extends StatelessWidget {
  final RehabApi api;
  const AccountPage({super.key, required this.api});
  @override
  Widget build(BuildContext context) =>
      ListView(padding: const EdgeInsets.all(20), children: [
        const Text('Cá nhân & bác sĩ',
            style: TextStyle(
                fontSize: 26, fontWeight: FontWeight.w700, color: ink)),
        const SizedBox(height: 24),
        DbView(
            api: api,
            path: 'patients/${api.uid}/profile',
            builder: (profile) => ProfileEditor(
                api: api,
                initialName: profile['name'] as String? ??
                    api.auth.currentUser?.displayName ??
                    '')),
        Panel(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(api.auth.currentUser?.email ?? '',
              style:
                  const TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          const Text(
              'Bạn quyết định bác sĩ nào được xem kết quả tập luyện của mình.',
              style: TextStyle(height: 1.5, color: Color(0xff5b7069))),
          const SizedBox(height: 18),
          FilledButton.icon(
              onPressed: () async {
                final qr = await Navigator.push<SetupQr>(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const QrPage(type: 'doctor')));
                if (qr == null || !context.mounted) return;
                try {
                  await api.linkDoctor(qr.id);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Đã liên kết bác sĩ.')));
                  }
                } catch (e) {
                  if (context.mounted) notice(context, e);
                }
              },
              icon: const Icon(Icons.qr_code_scanner),
              label: const Text('Liên kết bác sĩ')),
        ])),
        DbView(
            api: api,
            path: 'patientDoctors/${api.uid}',
            builder: (doctors) => Column(children: [
                  if (doctors.isEmpty)
                    const InfoBox(
                        'Chưa liên kết bác sĩ. Bạn có thể quét mã bác sĩ khi cần chia sẻ tiến độ.'),
                  ...doctors.keys.map((id) => Panel(
                      child: DbView(
                          api: api,
                          path: 'doctorDirectory/$id',
                          builder: (d) => Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(d['name'] ?? 'Bác sĩ',
                                        style: const TextStyle(
                                            fontSize: 18,
                                            fontWeight: FontWeight.w700)),
                                    TextButton(
                                        onPressed: () async {
                                          final confirm = await showDialog<
                                                  bool>(
                                              context: context,
                                              builder: (ctx) => AlertDialog(
                                                      title: const Text(
                                                          'Thu hồi quyền xem?'),
                                                      content: const Text(
                                                          'Bác sĩ này sẽ không còn xem dữ liệu hoặc ghi nhận xét mới cho bạn.'),
                                                      actions: [
                                                        TextButton(
                                                            onPressed: () =>
                                                                Navigator.pop(
                                                                    ctx, false),
                                                            child: const Text(
                                                                'Giữ liên kết')),
                                                        TextButton(
                                                            onPressed: () =>
                                                                Navigator.pop(
                                                                    ctx, true),
                                                            child: const Text(
                                                                'Thu hồi'))
                                                      ]));
                                          if (confirm != true) return;
                                          try {
                                            await api.revokeDoctor(id);
                                          } catch (e) {
                                            if (context.mounted) {
                                              notice(context, e);
                                            }
                                          }
                                        },
                                        child: const Text('Thu hồi quyền xem')),
                                  ])))),
                ])),
        const InfoBox(
            'Webcam được xử lý tại hub. Phiên bản này không ghi hoặc tải video của bạn lên cloud.'),
        OutlinedButton.icon(
            onPressed: () => api.auth.signOut(),
            icon: const Icon(Icons.logout),
            label: const Text('Đăng xuất')),
        const SizedBox(height: 16),
        const Center(
            child: Text('SMART REHAB · 1.0.0-rc2',
                style: TextStyle(color: Color(0xff5b7069)))),
      ]);
}

class ProfileEditor extends StatefulWidget {
  final RehabApi api;
  final String initialName;
  const ProfileEditor(
      {super.key, required this.api, required this.initialName});
  @override
  State<ProfileEditor> createState() => _ProfileEditorState();
}

class _ProfileEditorState extends State<ProfileEditor> {
  late final name = TextEditingController(text: widget.initialName);
  bool saving = false;
  @override
  void dispose() {
    name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Panel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Tên hiển thị với bác sĩ',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 17)),
        const SizedBox(height: 12),
        TextField(
            controller: name,
            maxLength: 100,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(labelText: 'Tên của bạn')),
        FilledButton(
            onPressed: saving
                ? null
                : () async {
                    setState(() => saving = true);
                    try {
                      await widget.api.saveProfile(name.text);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('Đã lưu tên của bạn.')));
                      }
                    } catch (error) {
                      if (context.mounted) notice(context, error);
                    } finally {
                      if (mounted) setState(() => saving = false);
                    }
                  },
            child: Text(saving ? 'Đang lưu…' : 'Lưu tên')),
      ]));
}
