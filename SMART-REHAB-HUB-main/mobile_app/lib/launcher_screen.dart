import 'dart:async';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'local_demo_auth.dart';
import 'home_screen.dart';
import 'workout_session.dart';

/// Opt-in loopback launcher, not pairing or a production authentication bypass.
class LauncherScreen extends StatefulWidget {
  const LauncherScreen({super.key});
  @override
  State<LauncherScreen> createState() => _LauncherScreenState();
}

class _LauncherScreenState extends State<LauncherScreen> {
  Timer? _timer;
  bool _busy = false, _authenticated = false;
  String? _sessionId;
  String _message = 'Chờ trang điều khiển SMART REHAB…';
  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds:1), (_) => _poll());
    unawaited(_poll());
  }
  Future<void> _poll() async {
    if (_busy) return;
    _busy = true;
    try {
      final state = await localLauncherState();
      final id = state['session_id'];
      if (state['enabled'] != true || id is! String || !validSessionId(id)) return;
      if (id == _sessionId) {await localLauncherReady(id);return;}
      if (!_authenticated) {
        final c = await localDemoCredentials();
        await FirebaseAuth.instance.signInWithEmailAndPassword(email:c['email']!,password:c['password']!);
        c.clear(); _authenticated = true;
      }
      // Permission check succeeds only after the Mac administrator granted ACL.
      await FirebaseDatabase.instance.ref('$configuredSessionRoot/$id/meta').get();
      if (!mounted) return;
      setState(() {_sessionId = id; _message = 'Đã kết nối';});
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(localLauncherReady(id).catchError((Object _) {}));
      });
    } catch (_) {
      if (mounted) setState(() => _message = 'Chưa kết nối được. Kiểm tra trạng thái ở trang điều khiển.');
    } finally {_busy = false;}
  }
  @override
  void dispose() {_timer?.cancel();super.dispose();}
  @override
  Widget build(BuildContext context) => _sessionId == null
    ? Scaffold(body:Center(child:Text(_message)))
    : HomeScreen(key:ValueKey(_sessionId),userName:'Demo',sessionId:_sessionId!,autoSaveTiming:true);
}
