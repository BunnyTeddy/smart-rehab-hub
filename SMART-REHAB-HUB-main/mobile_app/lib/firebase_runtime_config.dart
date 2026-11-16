import 'package:firebase_core/firebase_core.dart';

FirebaseOptions firebaseRuntimeOptions({
  required bool isWeb,
  required bool emulator,
  required bool integration,
  String appId = '',
  String apiKey = '',
}) {
  if (isWeb && integration && !emulator &&
      (!appId.contains(':web:') || apiKey.isEmpty)) {
    throw StateError('Set FIREBASE_APP_ID (registered Web app) and FIREBASE_API_KEY.');
  }
  return FirebaseOptions(
    apiKey: emulator ? 'demo-key' : apiKey.isNotEmpty ? apiKey : 'AIzaSyAyZFP_Pq_HzJy179dYNe2hsA5xoWGr0_Q',
    appId: emulator ? 'demo-app' : appId.isNotEmpty ? appId : '1:863483580594:android:769557d7bcf0882c5079ab',
    authDomain: 'smart-rehab-hub.firebaseapp.com',
    messagingSenderId: '863483580594',
    projectId: emulator ? 'demo-smart-rehab' : 'smart-rehab-hub',
    databaseURL: emulator ? 'https://demo-smart-rehab.firebaseio.com' :
        'https://smart-rehab-hub-default-rtdb.asia-southeast1.firebasedatabase.app',
  );
}
