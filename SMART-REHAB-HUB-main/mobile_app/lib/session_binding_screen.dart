import 'package:flutter/material.dart';
import 'home_screen.dart';
import 'workout_session.dart';

/// Explicit prototype selection; NOT secure device pairing.
class SessionBindingScreen extends StatefulWidget {
  final String userName;
  final bool offlineOnly;
  const SessionBindingScreen(
      {super.key, required this.userName, this.offlineOnly = false});
  @override
  State<SessionBindingScreen> createState() => _SessionBindingScreenState();
}

class _SessionBindingScreenState extends State<SessionBindingScreen> {
  final _id = TextEditingController();
  String? _error;
  @override
  void dispose() {
    _id.dispose();
    super.dispose();
  }

  void _open({required bool demo}) {
    final id = demo ? 'demo_fixture' : _id.text.trim();
    if (!validSessionId(id)) {
      setState(() => _error = 'Use letters, numbers, _ or - for session ID');
      return;
    }
    Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(
            builder: (_) => HomeScreen(
                userName: widget.userName, sessionId: id, demo: demo)),
        (_) => false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Prototype session binding')),
        body: ListView(padding: const EdgeInsets.all(24), children: [
          const Text('Observe an existing Pi session',
              style: TextStyle(fontSize: 24)),
          const SizedBox(height: 16),
          const Text(
              'Paste the exact session ID printed by the Pi. This does not scan a QR, pair a device, or start/change an exercise. Access still depends on Firebase rules.'),
          const SizedBox(height: 16),
          TextField(
              controller: _id,
              decoration:
                  InputDecoration(labelText: 'Session ID', errorText: _error)),
          const SizedBox(height: 16),
          ElevatedButton(
              onPressed: widget.offlineOnly ? null : () => _open(demo: false),
              child: Text(widget.offlineOnly
                  ? 'Cloud disabled in offline demo'
                  : 'Observe session')),
          OutlinedButton(
              onPressed: () => _open(demo: true),
              child: const Text('Use offline demo fixture')),
        ]),
      );
}
