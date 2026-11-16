import 'package:flutter_test/flutter_test.dart';
import '../lib/firebase_runtime_config.dart';

void main() {
  test('Web integration requires explicit Web ID and key', () {
    for (final id in ['', '1:123:android:abc', '1:123:web:abc']) {
      expect(() => firebaseRuntimeOptions(isWeb:true, emulator:false, integration:true, appId:id), throwsStateError);
    }
  });
  test('Web options use the provided key, never the Android fallback', () {
    final config = firebaseRuntimeOptions(isWeb:true, emulator:false, integration:true,
        appId:'1:123:web:abc', apiKey:'web-config-key');
    expect(config.apiKey, 'web-config-key');
    expect(config.appId, '1:123:web:abc');
    expect(config.projectId, 'smart-rehab-hub');
  });
  test('Emulator stays isolated and legacy native remains compatible', () {
    expect(firebaseRuntimeOptions(isWeb:true, emulator:true, integration:true).projectId, 'demo-smart-rehab');
    expect(firebaseRuntimeOptions(isWeb:false, emulator:false, integration:false).appId, contains(':android:'));
  });
}
