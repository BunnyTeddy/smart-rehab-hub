"""BLE provisioning packets. QR key is random 256-bit; never a short PIN."""
import base64
import json
import secrets
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .protocol import dumps, safe_id


def b64(value):
    return base64.b64encode(value).decode('ascii')


def unb64(value):
    return base64.b64decode(value, validate=True)


class SecureChannel:
    def __init__(self, hub_id, key, *, challenge=None, clock=time.monotonic):
        self.hub_id = safe_id(hub_id)
        self.key = unb64(key) if isinstance(key, str) else key
        if len(self.key) != 32:
            raise ValueError('invalid_setup_key')
        self.challenge = challenge or secrets.token_hex(16)
        self.clock, self.started, self.received, self.sent = clock, clock(), 0, 0

    def aad(self, direction, sequence):
        return f'smart-rehab:v1|{self.hub_id}|{self.challenge}|{direction}|{sequence}'.encode()

    def encrypt(self, value, direction='response'):
        self.sent += 1
        nonce = secrets.token_bytes(12)
        payload = AESGCM(self.key).encrypt(nonce, dumps(value).encode(), self.aad(direction, self.sent))
        return dumps({'seq': self.sent, 'nonce': b64(nonce), 'data': b64(payload)}).encode()

    def decrypt(self, packet, direction='request'):
        if self.clock() - self.started > 120:
            raise ValueError('provisioning_expired')
        if len(packet) > 12000:
            raise ValueError('packet_too_large')
        envelope = json.loads(packet)
        sequence = envelope.get('seq')
        if type(sequence) is not int or sequence != self.received + 1:
            raise ValueError('replayed_or_out_of_order_packet')
        nonce = unb64(envelope['nonce'])
        if len(nonce) != 12:
            raise ValueError('invalid_nonce')
        clear = AESGCM(self.key).decrypt(nonce, unb64(envelope['data']), self.aad(direction, sequence))
        result = json.loads(clear)
        if not isinstance(result, dict):
            raise ValueError('invalid_packet')
        self.received = sequence
        return result


class PacketAssembler:
    """One header byte: 1=start, 2=middle, 3=end, 4=single."""
    def __init__(self, max_bytes=12000):
        self.buffer = bytearray()
        self.active = False
        self.max_bytes = max_bytes

    def feed(self, chunk):
        if not chunk:
            raise ValueError('empty_chunk')
        flag, payload = chunk[0], chunk[1:]
        if flag in (1, 4):
            self.buffer.clear()
            self.active = True
        elif flag not in (2, 3) or not self.active:
            raise ValueError('invalid_chunk_order')
        self.buffer.extend(payload)
        if len(self.buffer) > self.max_bytes:
            self.buffer.clear(); self.active = False
            raise ValueError('packet_too_large')
        if flag in (3, 4):
            result = bytes(self.buffer)
            self.buffer.clear(); self.active = False
            return result
        return None


def chunks(packet, payload_size=18):
    blocks = [packet[i:i + payload_size] for i in range(0, len(packet), payload_size)]
    for i, block in enumerate(blocks):
        flag = 4 if len(blocks) == 1 else 1 if i == 0 else 3 if i == len(blocks) - 1 else 2
        yield bytes([flag]) + block
