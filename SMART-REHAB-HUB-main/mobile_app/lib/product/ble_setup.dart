import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_reactive_ble/flutter_reactive_ble.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:permission_handler/permission_handler.dart';
import 'contract.dart';
import 'secure_channel.dart';
import 'api.dart';

class BleSetup {
  final FlutterReactiveBle ble = FlutterReactiveBle();
  final FlutterSecureStorage storage = const FlutterSecureStorage(
      aOptions: AndroidOptions(encryptedSharedPreferences: true));
  Future<void> configure(SetupQr qr, String ssid, String password,
      void Function(String) progress) async {
    final profile = asMap((await RehabApi()
            .ref('patients/${FirebaseAuth.instance.currentUser!.uid}/profile')
            .get())
        .value);
    if (profile['name'] is! String ||
        (profile['name'] as String).trim().isEmpty) {
      throw StateError(
          'Hãy vào mục Cá nhân, lưu tên của bạn rồi ghép hub lại nhé.');
    }
    final permissions = await [
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.locationWhenInUse
    ].request();
    if (!permissions.values.any((s) => s.isGranted)) {
      throw StateError('Cần cho phép Bluetooth để tìm hub ở gần bạn.');
    }
    final status = await ble.statusStream
        .firstWhere((s) => s != BleStatus.unknown)
        .timeout(const Duration(seconds: 10));
    if (status != BleStatus.ready) {
      throw StateError(
          'Hãy bật Bluetooth và quyền Thiết bị ở gần. Với Android cũ, hãy bật thêm Vị trí.');
    }
    final user = FirebaseAuth.instance.currentUser!;
    progress('Đang tìm hub ở gần bạn…');
    final device = await ble
        .scanForDevices(
            withServices: [Uuid.parse(serviceUuid)],
            scanMode: ScanMode.lowLatency)
        .firstWhere((d) =>
            d.name == 'Rehab-${qr.id.substring(max(0, qr.id.length - 6))}')
        .timeout(const Duration(seconds: 25));
    final connected = Completer<void>();
    final connection = ble
        .connectToDevice(
            id: device.id, connectionTimeout: const Duration(seconds: 15))
        .listen((state) {
      if (state.connectionState == DeviceConnectionState.connected &&
          !connected.isCompleted) {
        connected.complete();
      }
      if (state.connectionState == DeviceConnectionState.disconnected &&
          !connected.isCompleted) {
        connected.completeError(StateError('Hub đã ngắt Bluetooth.'));
      }
    }, onError: (Object e) {
      if (!connected.isCompleted) connected.completeError(e);
    });
    StreamSubscription<List<int>>? notifications;
    try {
      await connected.future;
      progress('Đang xác minh mã ghép hub…');
      int mtu = 23;
      try {
        mtu = await ble.requestMtu(deviceId: device.id, mtu: 247);
      } catch (_) {/* Default ATT MTU remains usable. */}
      QualifiedCharacteristic characteristic(String id) =>
          QualifiedCharacteristic(
              serviceId: Uuid.parse(serviceUuid),
              characteristicId: Uuid.parse(id),
              deviceId: device.id);
      final response = Completer<List<int>>();
      final assembler = PacketAssembler();
      notifications = ble
          .subscribeToCharacteristic(characteristic(responseUuid))
          .listen((bytes) {
        try {
          final packet = assembler.feed(bytes);
          if (packet != null && !response.isCompleted) {
            response.complete(packet);
          }
        } catch (e) {
          if (!response.isCompleted) response.completeError(e);
        }
      }, onError: (Object e) {
        if (!response.isCompleted) response.completeError(e);
      });
      final header = asMap(jsonDecode(utf8.decode(
          await ble.readCharacteristic(characteristic(challengeUuid)))));
      if (header['hub_id'] != qr.id || header['version'] != 1) {
        throw StateError('Hub ở gần không khớp với mã QR.');
      }
      final storageKey = 'owner:${user.uid}:${qr.id}';
      var ownerKey = await storage.read(key: storageKey);
      if (header['paired'] == true && ownerKey == null) {
        throw StateError(
            'Điện thoại này chưa có khóa của chủ hub. Cần khôi phục khóa qua quản trị viên.');
      }
      ownerKey ??= ProvisioningChannel.newKey();
      await storage.write(key: storageKey, value: ownerKey);
      // Retain the QR only inside platform-protected storage, for changing Wi-Fi later.
      await storage.write(
          key: 'qr:${user.uid}:${qr.id}',
          value: jsonEncode(
              {'v': 1, 'type': 'hub', 'hub_id': qr.id, 'key': qr.key}));
      final channel = ProvisioningChannel(qr.id, header['challenge'] as String,
          header['paired'] == true ? ownerKey : qr.key!);
      final token = await user.getIdToken(true);
      final request = await channel.encrypt({
        'ssid': ssid,
        'password': password,
        'id_token': token,
        'owner_key': ownerKey
      });
      progress('Đang kết nối Wi-Fi và xác nhận tài khoản…');
      for (final chunk in packetChunks(request, size: min(220, mtu - 4))) {
        await ble.writeCharacteristicWithResponse(characteristic(requestUuid),
            value: chunk);
      }
      final result = await channel
          .decrypt(await response.future.timeout(const Duration(seconds: 95)));
      if (result['ok'] != true) throw StateError(reasonText(result['code']));
      progress('Đã kết nối hub với tài khoản của bạn.');
    } on TimeoutException {
      throw StateError(
          'Chưa nhận được phản hồi từ hub. Đưa điện thoại lại gần rồi thử lại; cấu hình cũ vẫn được giữ.');
    } finally {
      await notifications?.cancel();
      await connection.cancel();
    }
  }

  Future<SetupQr?> savedQr(String hub) async {
    final uid = FirebaseAuth.instance.currentUser!.uid;
    final text = await storage.read(key: 'qr:$uid:$hub');
    return text == null ? null : SetupQr.parse(text, 'hub');
  }
}
