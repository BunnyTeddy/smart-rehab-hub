import json
import tempfile
import unittest
from pathlib import Path
from product_v1.protocol import validate_command
from product_v1.secure_channel import SecureChannel, PacketAssembler, chunks, b64
from product_v1.state import Store


class ContractTests(unittest.TestCase):
    def test_commands_are_owned_bounded_and_expire(self):
        c = dict(action='start', patient_uid='p1', exercise='squat', duration_s=180,
                 created_at=1000, expires_at=31000)
        self.assertEqual(validate_command(c, 'p1', 2000), c)
        for change, owner, now in [({}, 'p2', 2000), ({}, 'p1', 31000),
                                  ({'duration_s': 999}, 'p1', 2000),
                                  ({'created_at': 9000}, 'p1', 2000),
                                  ({'expires_at': 32000}, 'p1', 2000)]:
            with self.assertRaises(ValueError): validate_command({**c, **change}, owner, now)

    def test_authenticated_packets_cross_direction_and_replay(self):
        a = SecureChannel('hub1', bytes(range(32)), challenge='test')
        b = SecureChannel('hub1', bytes(range(32)), challenge='test')
        packet = a.encrypt({'ssid': 'Mạng thử', 'password': 'test'}, 'request')
        self.assertEqual(b.decrypt(packet)['ssid'], 'Mạng thử')
        with self.assertRaises(ValueError): b.decrypt(packet)
        with self.assertRaises(Exception): SecureChannel('hub1', b'x' * 32, challenge='test').decrypt(packet)
        with self.assertRaises(Exception): SecureChannel('hub1', bytes(range(32)), challenge='other').decrypt(packet)
        with self.assertRaises(Exception): SecureChannel('hub1', bytes(range(32)), challenge='test').decrypt(packet, 'response')

    def test_authentication_failure_does_not_consume_sequence(self):
        a = SecureChannel('hub1', b'x' * 32, challenge='a')
        b = SecureChannel('hub1', b'x' * 32, challenge='a')
        packet = a.encrypt({'token': 'test'}, 'request')
        bad = json.loads(packet); bad['data'] = b64(b'not authentic')
        with self.assertRaises(Exception): b.decrypt(json.dumps(bad).encode())
        self.assertEqual(b.received, 0)
        self.assertEqual(b.decrypt(packet), {'token': 'test'})

    def test_provisioning_expires_and_chunks_are_bounded(self):
        now = [0]
        a = SecureChannel('hub1', b'x' * 32, clock=lambda: now[0])
        now[0] = 121
        with self.assertRaisesRegex(ValueError, 'expired'): a.decrypt(b'{}')
        for payload in [b'x', b'abc' * 2000]:
            assembler = PacketAssembler(); result = None
            for part in chunks(payload):
                self.assertLessEqual(len(part), 19)
                result = assembler.feed(part)
            self.assertEqual(result, payload)
        with self.assertRaises(ValueError): PacketAssembler().feed(b'\x03end')
        with self.assertRaises(ValueError): PacketAssembler(2).feed(b'\x04xxxx')

    def test_outbox_and_command_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'state.db'; s = Store(p)
            s.accept('cmd1', {'status': 'accepted'}, {'session_id': 's1'})
            s.enqueue('sessions/s1/meta', {'id': 's1'})
            s.close(); s = Store(p)
            self.assertEqual(s.acknowledgement('cmd1'), {'status': 'accepted'})
            self.assertEqual(s.get('active')['session_id'], 's1')
            self.assertEqual(s.pending()[1], 'sessions/s1/meta')
            with self.assertRaises(ValueError): s.enqueue('sessions/s1/meta', {'id': 's2'})
            with self.assertRaises(Exception): s.accept('cmd1', {'status': 'accepted'})
            s.close()

    def test_ack_does_not_drop_newer_index_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'state.db')
            s.enqueue('index/s1', {'reps': 0}, replace=True); old = s.pending()
            s.enqueue('index/s1', {'reps': 3}, replace=True); s.sent(old)
            self.assertEqual(s.pending()[2], {'reps': 3})
            s.sent(s.pending()); self.assertEqual(s.count(), 0); s.close()
