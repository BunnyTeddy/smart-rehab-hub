// Test harness only. Never enabled in a production/hosted build.
// ignore: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;
import 'dart:convert';

Future<Map<String, String>> localDemoCredentials() async {
  if (Uri.base.host != '127.0.0.1') throw StateError('Loopback only');
  final response = await html.HttpRequest.request('/__demo_login', method: 'POST',
      requestHeaders: {'X-Rehab-Demo': 'local-only'});
  if (response.status != 200) throw StateError('Credential not ready');
  final value = jsonDecode(response.responseText!) as Map<String, dynamic>;
  return {'email': value['email'] as String, 'password': value['password'] as String};
}

Future<void> saveLocalTiming(String value) async {
  if (Uri.base.host != '127.0.0.1') throw StateError('Loopback only');
  final response = await html.HttpRequest.request('/__timing', method: 'POST',
      requestHeaders: {'X-Rehab-Demo': 'local-only'}, sendData: value);
  if (response.status != 200) throw StateError('Timing save failed');
}

Future<Map<String, dynamic>> localLauncherState() async {
  if (Uri.base.host != '127.0.0.1') throw StateError('Loopback only');
  final response = await html.HttpRequest.request('/__launcher');
  return jsonDecode(response.responseText!) as Map<String, dynamic>;
}

Future<void> localLauncherReady(String sessionId) async {
  if (Uri.base.host != '127.0.0.1') throw StateError('Loopback only');
  await html.HttpRequest.request('/__launcher_ready', method: 'POST',
    requestHeaders: {'X-Rehab-Demo': 'local-only'},
    sendData: jsonEncode({'session_id':sessionId}));
}
