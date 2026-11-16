import 'dart:convert';
import 'dart:math';
import 'package:cryptography/cryptography.dart';

class ProvisioningChannel {
  final String hubId, challenge;
  final SecretKey key;
  int sent = 0, received = 0;
  final AesGcm cipher = AesGcm.with256bits();
  ProvisioningChannel(this.hubId, this.challenge, String encodedKey)
      : key = SecretKey(base64Decode(encodedKey));
  static String newKey() =>
      base64Encode(List.generate(32, (_) => Random.secure().nextInt(256)));
  List<int> aad(String direction, int sequence) =>
      utf8.encode('smart-rehab:v1|$hubId|$challenge|$direction|$sequence');
  Future<List<int>> encrypt(Map<String, dynamic> value) async {
    final sequence = ++sent;
    final box = await cipher.encrypt(utf8.encode(jsonEncode(value)),
        secretKey: key, aad: aad('request', sequence));
    return utf8.encode(jsonEncode({
      'seq': sequence,
      'nonce': base64Encode(box.nonce),
      'data': base64Encode([...box.cipherText, ...box.mac.bytes])
    }));
  }

  Future<Map<String, dynamic>> decrypt(List<int> bytes) async {
    if (bytes.length > 12000) {
      throw const FormatException('Gói dữ liệu quá lớn');
    }
    final data = jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
    final sequence = data['seq'];
    if (sequence is! int || sequence != received + 1) {
      throw const FormatException('Gói dữ liệu không đúng thứ tự');
    }
    final encrypted = base64Decode(data['data'] as String);
    if (encrypted.length < 16) {
      throw const FormatException('Gói dữ liệu chưa hợp lệ');
    }
    final box = SecretBox(encrypted.sublist(0, encrypted.length - 16),
        nonce: base64Decode(data['nonce']),
        mac: Mac(encrypted.sublist(encrypted.length - 16)));
    final clear = await cipher.decrypt(box,
        secretKey: key, aad: aad('response', sequence));
    final result = jsonDecode(utf8.decode(clear)) as Map<String, dynamic>;
    received = sequence;
    return result;
  }
}

Iterable<List<int>> packetChunks(List<int> packet, {int size = 18}) sync* {
  if (size < 1) throw ArgumentError.value(size);
  for (var offset = 0; offset < packet.length; offset += size) {
    final end = min(packet.length, offset + size);
    final flag = offset == 0
        ? (end == packet.length ? 4 : 1)
        : end == packet.length
            ? 3
            : 2;
    yield [flag, ...packet.sublist(offset, end)];
  }
}

class PacketAssembler {
  final List<int> _buffer = [];
  bool _active = false;
  List<int>? feed(List<int> bytes) {
    if (bytes.isEmpty) throw const FormatException('Gói dữ liệu trống');
    final flag = bytes.first;
    if (flag == 1 || flag == 4) {
      _buffer.clear();
      _active = true;
    } else if (!_active || (flag != 2 && flag != 3)) {
      throw const FormatException('Sai thứ tự gói dữ liệu');
    }
    _buffer.addAll(bytes.skip(1));
    if (_buffer.length > 12000) {
      _buffer.clear();
      _active = false;
      throw const FormatException('Gói dữ liệu quá lớn');
    }
    if (flag == 3 || flag == 4) {
      final result = List<int>.of(_buffer);
      _buffer.clear();
      _active = false;
      return result;
    }
    return null;
  }
}
