import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/session_binding_screen.dart';
import 'package:mobile_app/main.dart';
import 'package:mobile_app/splash_screen.dart';
import 'package:mobile_app/login_screen.dart';

void main() {
  testWidgets('splash reaches login without DNS or Internet probe', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: SplashScreen()));
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.text('No Internet Connection'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('offline app boots without Firebase and cloud button is disabled',
      (tester) async {
    await tester.pumpWidget(const SmartRehabApp(demo: true));
    expect(find.text('Use offline demo fixture'), findsOneWidget);
    final cloud = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, 'Cloud disabled in offline demo'));
    expect(cloud.onPressed, isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('Prototype requires an explicit valid session ID',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: SessionBindingScreen(userName: 'Test'),
    ));
    expect(find.text('Use offline demo fixture'), findsOneWidget);
    await tester.tap(find.text('Observe session'));
    await tester.pump();
    expect(find.text('Use letters, numbers, _ or - for session ID'),
        findsOneWidget);
    await tester.enterText(find.byType(TextField), '../current_session');
    await tester.tap(find.text('Observe session'));
    await tester.pump();
    expect(find.byType(SessionBindingScreen), findsOneWidget);
  });
}
