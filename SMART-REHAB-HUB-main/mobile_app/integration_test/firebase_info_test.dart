import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mobile_app/firebase_runtime_config.dart';

// Read-only native Android regression check. No login, patient data, writes,
// or commands to a real hub. Run on an Android device with Internet access.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
      'Android reads Firebase connection and clock from local info tree',
      (tester) async {
    await Firebase.initializeApp(
      options: firebaseRuntimeOptions(
        isWeb: false,
        emulator: false,
        integration: false,
        appId: '1:863483580594:android:55a0e0ca5bb900d25079ab',
      ),
    );
    final db = FirebaseDatabase.instance;
    final connected = await db
        .ref('.info/connected')
        .onValue
        .firstWhere((event) => event.snapshot.value == true)
        .timeout(const Duration(seconds: 30));
    expect(connected.snapshot.value, isTrue);

    final offset = await db
        .ref('.info/serverTimeOffset')
        .onValue
        .first
        .timeout(const Duration(seconds: 10));
    expect(offset.snapshot.value, isA<num>());

    // The old start path used get(). Reproduce its server-side rejection on
    // the same SDK/configuration, despite the local listener being connected.
    await expectLater(
      db.ref('.info/connected').get().timeout(const Duration(seconds: 15)),
      throwsA(isA<FirebaseException>()),
    );
  });
}
