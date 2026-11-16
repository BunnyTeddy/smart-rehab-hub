// lib/main.dart (FULL SOURCE - DIRECT FIREBASE CONFIG - ANTI-HANG)
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'splash_screen.dart';
import 'session_binding_screen.dart';
import 'firebase_runtime_config.dart';
import 'launcher_screen.dart';
import 'product/app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (const bool.fromEnvironment('REHAB_DEMO')) {
    runApp(const SmartRehabApp(demo: true));
    return;
  }

  // KHỞI TẠO FIREBASE TRỰC TIẾP QUA OPTIONS (VƯỢT QUA 100% LỖI ANDROID VALUES.XML)
  try {
    const emulator = bool.fromEnvironment('REHAB_EMULATOR');
    const webAppId = String.fromEnvironment('FIREBASE_APP_ID',
        defaultValue: '1:863483580594:android:55a0e0ca5bb900d25079ab');
    const integration =
        String.fromEnvironment('REHAB_SESSION_ROOT') == 'demo_e2e_v1/sessions';
    await Firebase.initializeApp(
      options: firebaseRuntimeOptions(
        isWeb: kIsWeb,
        emulator: emulator,
        integration: integration,
        appId: kIsWeb && !integration
            ? '1:863483580594:web:41e7be53c73738775079ab'
            : webAppId,
        apiKey: const String.fromEnvironment('FIREBASE_API_KEY',
            defaultValue: kIsWeb
                ? 'AIzaSyCIhOntftB7QlhPdrYNDX_DQtXY3MwL8VI'
                : 'AIzaSyAyZFP_Pq_HzJy179dYNe2hsA5xoWGr0_Q'),
      ),
    );
    if (const bool.fromEnvironment('REHAB_EMULATOR')) {
      await FirebaseAuth.instance.useAuthEmulator('127.0.0.1', 9099);
      FirebaseDatabase.instance.useDatabaseEmulator('127.0.0.1', 9000);
    }
  } catch (e) {
    runApp(MaterialApp(
        home: Scaffold(
            body: Center(
                child: SelectableText(
                    'Chưa mở được SMART REHAB. Hãy kiểm tra kết nối Internet và mở lại ứng dụng.',
                    textAlign: TextAlign.center)))));
    return;
  }

  runApp(const bool.fromEnvironment('REHAB_LAUNCHER') ||
          const bool.fromEnvironment('REHAB_LEGACY')
      ? const SmartRehabApp()
      : const ProductApp());
}

// ==========================================
// GLOBAL DESIGN SYSTEM (COLORS & THEME)
// ==========================================
class AppColors {
  static const Color background = Color(0xFFFFFFFF); // Pure White
  static const Color primary = Color(0xFF10B981); // Emerald Green
  static const Color textDark = Color(0xFF1E293B); // Dark Slate Text
  static const Color textGray = Color(0xFF94A3B8); // Light Gray Text
  static const Color cardBg = Color(0xFFF8FAFC); // Very Light Gray
}

class SmartRehabApp extends StatelessWidget {
  final bool demo;
  const SmartRehabApp({super.key, this.demo = false});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Rehab 5G',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        scaffoldBackgroundColor: AppColors.background,
        textTheme: demo
            ? Theme.of(context).textTheme
            : GoogleFonts.interTextTheme(Theme.of(context).textTheme),
        colorScheme: ColorScheme.fromSeed(seedColor: AppColors.primary),
        useMaterial3: true,
      ),
      home: demo
          ? const SessionBindingScreen(userName: 'Demo', offlineOnly: true)
          : const bool.fromEnvironment('REHAB_LAUNCHER')
              ? const LauncherScreen()
              : const SplashScreen(),
    );
  }
}
