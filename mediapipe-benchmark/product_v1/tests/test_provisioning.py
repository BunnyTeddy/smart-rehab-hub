"""Failure-path checks without changing the developer or hub Wi-Fi."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from dbus_fast import Variant
from product_v1.ble import Provisioner
from product_v1.network import NetworkChange, BUS, PATH
from product_v1.secure_channel import SecureChannel, b64


class ProvisioningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'config.json'
        self.config = {'setup_key': b64(b'q' * 32)}
        self.cloud = SimpleNamespace(last_success=time.monotonic(), verify_patient=Mock(return_value='p1'),
                                     patient_hub=Mock(return_value=None), get=Mock(return_value={}), request=Mock())
        self.hub = SimpleNamespace(lock=threading.RLock(), session=None, provisioning=False,
                                   owner=None, id='h1', cloud=self.cloud, store=SimpleNamespace(set=Mock()))
        self.provisioner = Provisioner(self.hub, self.config, self.path, None)
        self.provisioner.response = SimpleNamespace(publish=Mock())
        self.channel = Mock(wraps=SecureChannel('h1', b'q' * 32))
        self.network = SimpleNamespace(activate=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        self.request = dict(ssid='Test network', password='test-only', id_token='test', owner_key=b64(b'o' * 32))

    def tearDown(self):
        self.tmp.cleanup()

    async def run_request(self):
        with patch('product_v1.ble.NetworkChange', return_value=self.network), patch('product_v1.ble.asyncio.sleep', new=AsyncMock()):
            await self.provisioner.configure(self.request, self.channel)
        self.assertFalse(self.provisioner.busy)
        self.assertFalse(self.hub.provisioning)
        return self.channel.encrypt.call_args.args[0]

    async def test_wrong_owner_never_switches_wifi(self):
        self.config['owner_uid'] = 'actual-owner'
        result = await self.run_request()
        self.assertEqual(result['code'], 'hub_has_another_owner')
        self.network.activate.assert_not_awaited()
        self.cloud.request.assert_not_called()

    async def test_wrong_wifi_preserves_pairing_and_returns_error(self):
        self.config.update(owner_uid='p1', owner_key=self.request['owner_key'])
        original = self.config.copy()
        self.network.activate.side_effect = ValueError('wifi_connection_failed')
        result = await self.run_request()
        self.assertEqual(result['code'], 'wifi_connection_failed')
        self.assertEqual(original, self.config)
        self.network.rollback.assert_awaited_once()
        self.cloud.request.assert_not_called()

    async def test_existing_patient_hub_does_not_rotate_qr_key(self):
        self.cloud.patient_hub.return_value = 'another-hub'
        result = await self.run_request()
        self.assertEqual(result['code'], 'patient_has_another_hub')
        self.assertNotIn('owner_key', self.config)
        self.network.rollback.assert_awaited_once()
        self.cloud.request.assert_not_called()

    async def test_failed_cloud_claim_keeps_owner_recovery_key_and_retry_is_idempotent(self):
        self.cloud.request.side_effect = RuntimeError('firebase_network_unavailable')
        self.assertFalse((await self.run_request())['ok'])
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['pending_owner_uid'], 'p1')
        self.assertEqual(saved['owner_key'], self.request['owner_key'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertIsNone(self.hub.owner)
        self.network.commit.assert_not_awaited()
        self.cloud.request.side_effect = None
        self.assertTrue((await self.run_request())['ok'])
        self.assertEqual(self.hub.owner, 'p1')
        self.assertIsNone(self.config['pending_owner_uid'])
        self.network.commit.assert_awaited_once()

    async def test_pairing_during_session_does_not_touch_network(self):
        self.hub.session = object()
        self.assertEqual((await self.run_request())['code'], 'session_active')
        self.network.activate.assert_not_awaited()
        self.cloud.verify_patient.assert_not_called()


class WifiTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_new_network_restores_old_and_deletes_only_temporary_profile(self):
        manager = SimpleNamespace(call_get_device_by_ip_iface=AsyncMock(return_value='/wifi'), call_activate_connection=AsyncMock())
        settings = SimpleNamespace(call_add_connection=AsyncMock(return_value='/new-profile'))
        device = SimpleNamespace(call_get=AsyncMock(side_effect=[Variant('o', '/old-active'), Variant('u', 120), Variant('o', '/')]))
        active = SimpleNamespace(call_get=AsyncMock(return_value=Variant('o', '/old-profile')))
        temporary = SimpleNamespace(call_delete=AsyncMock())
        objects = {PATH: manager, PATH+'/Settings': settings, '/wifi': device, '/old-active': active, '/new-profile': temporary}
        async def get_interface(bus, path, name):
            return objects[path]
        network = NetworkChange(None)
        with patch('product_v1.network.interface', side_effect=get_interface):
            with self.assertRaisesRegex(ValueError, 'wifi_connection_failed'):
                await network.activate('New Wi-Fi', 'wrong-password')
        self.assertEqual([c.args[0] for c in manager.call_activate_connection.await_args_list], ['/new-profile', '/old-profile'])
        temporary.call_delete.assert_awaited_once()
        self.assertIsNone(network.profile)
        self.assertFalse(settings.call_add_connection.call_args.args[0]['connection']['autoconnect'].value)
