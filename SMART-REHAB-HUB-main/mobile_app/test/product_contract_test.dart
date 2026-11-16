import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/product/secure_channel.dart';
import 'package:mobile_app/product/contract.dart';
import 'package:mobile_app/product/app.dart';

void main() {
  test('Dart authenticates the actual Python AES-GCM packet and rejects replay', () async {
    final fixture = jsonDecode(File('test/fixtures/ble_python_packet.json').readAsStringSync());
    final channel = ProvisioningChannel(fixture['hub_id'], fixture['challenge'], fixture['key']);
    final packet = utf8.encode(jsonEncode(fixture['packet']));
    expect(await channel.decrypt(packet), fixture['expected']);
    await expectLater(channel.decrypt(packet), throwsFormatException);
    final wrong = ProvisioningChannel(fixture['hub_id'], 'another-challenge', fixture['key']);
    await expectLater(wrong.decrypt(packet), throwsA(isA<Exception>()));
  });
  test('ATT packets fit default MTU and reassemble Vietnamese data', () {
    final packet = utf8.encode(jsonEncode({'ssid': 'Mạng gia đình', 'token': 'a' * 8000}));
    final assembler = PacketAssembler(); List<int>? output;
    for (final part in packetChunks(packet)) { expect(part.length, lessThanOrEqualTo(19)); output = assembler.feed(part); }
    expect(output, packet);
    expect(() => PacketAssembler().feed([3, 1]), throwsFormatException);
  });
  test('QR validates destination, type and full entropy key', () {
    expect(SetupQr.parse(jsonEncode({'v': 1, 'type': 'doctor', 'doctor_uid': 'doctor_1'}), 'doctor').id, 'doctor_1');
    expect(() => SetupQr.parse('{"v":1,"type":"doctor","doctor_uid":"../users"}', 'doctor'), throwsFormatException);
    expect(() => SetupQr.parse('{"v":1,"type":"hub","hub_id":"hub1","key":"AAAA"}', 'hub'), throwsFormatException);
    expect(() => SetupQr.parse('{"v":1,"type":"doctor","doctor_uid":"d1"}', 'hub'), throwsFormatException);
  });
  testWidgets('Vietnamese sign in and registration fit a narrow Android screen', (tester) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const MaterialApp(home: SignInPage()));
    expect(find.text('Đăng nhập'), findsOneWidget);
    await tester.ensureVisible(find.text('Chưa có tài khoản? Đăng ký'));
    await tester.tap(find.text('Chưa có tài khoản? Đăng ký')); await tester.pump();
    expect(find.text('Tên của bạn'), findsOneWidget);
    await tester.ensureVisible(find.text('Tạo tài khoản')); await tester.tap(find.text('Tạo tài khoản')); await tester.pump();
    expect(find.text('Nhập tên từ 1 đến 100 ký tự.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
