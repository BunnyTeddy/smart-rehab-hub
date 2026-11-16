"""BlueZ GATT provisioning. Secrets never enter shell arguments or log messages."""
import asyncio
import json
import logging
import os
import threading
import time
from dbus_fast import Variant, BusType, PropertyAccess, DBusError
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, dbus_property
from .network import NetworkChange
from .protocol import ROOT, SERVICE_UUID, CHALLENGE_UUID, REQUEST_UUID, RESPONSE_UUID, dumps
from .secure_channel import SecureChannel, PacketAssembler, chunks, unb64

BASE = '/com/smartrehab/provision'
SERVICE = BASE + '/service0'
BLUEZ = 'org.bluez'
LOG = logging.getLogger('smart-rehab.ble')


class Provisioner:
    def __init__(self, hub, config, config_path, bus):
        self.hub, self.config, self.config_path, self.bus = hub, config, config_path, bus
        self.channel, self.device, self.assembler = None, None, PacketAssembler()
        self.busy = False
        self.response = None
        self.header = None

    def challenge(self, options):
        device = options.get('device', Variant('o', '/')).value
        offset = options.get('offset', Variant('q', 0)).value
        if self.busy or (self.device and self.device != device and self.channel and time.monotonic() - self.channel.started < 120):
            raise DBusError('org.bluez.Error.InProgress', 'Provisioning is busy')
        if offset == 0:
            paired = bool(self.hub.owner or self.config.get('owner_key'))
            key = self.config.get('owner_key') if paired else self.config['setup_key']
            if not key:
                raise DBusError('org.bluez.Error.NotAuthorized', 'Technician recovery required')
            self.channel = SecureChannel(self.hub.id, key)
            self.device, self.assembler = device, PacketAssembler()
            self.header = dumps(dict(version=1, hub_id=self.hub.id, challenge=self.channel.challenge, paired=paired)).encode()
        if self.header is None:
            raise DBusError('org.bluez.Error.InvalidOffset', 'Read challenge first')
        return self.header[offset:]

    def receive(self, value, options):
        device = options.get('device', Variant('o', '/')).value
        if not self.channel or self.device != device or self.busy:
            raise DBusError('org.bluez.Error.NotAuthorized', 'Read challenge first')
        try:
            packet = self.assembler.feed(bytes(value))
            if packet is not None:
                request = self.channel.decrypt(packet)
                self.busy = True
                asyncio.create_task(self.configure(request, self.channel))
        except Exception:
            raise DBusError('org.bluez.Error.NotAuthorized', 'Invalid provisioning packet') from None

    def save(self, **values):
        self.config.update(values)
        temp = self.config_path.with_suffix('.new')
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(dumps(self.config)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, self.config_path)

    async def configure(self, request, channel):
        network = NetworkChange(self.bus)
        result = {'ok': False, 'code': 'provisioning_failed'}
        try:
            with self.hub.lock:
                if self.hub.session:
                    raise ValueError('session_active')
                self.hub.provisioning = True
            owner_key = request.get('owner_key')
            if not self.config.get('owner_key') and (not isinstance(owner_key, str) or len(unb64(owner_key)) != 32):
                raise ValueError('invalid_owner_key')
            # Verification before switching, when the old network is available, catches theft early.
            expected = self.config.get('owner_uid') or self.config.get('pending_owner_uid') or self.hub.owner
            if expected and self.hub.cloud.last_success and time.monotonic() - self.hub.cloud.last_success < 10:
                uid = await asyncio.to_thread(self.hub.cloud.verify_patient, request.get('id_token'))
                if uid != expected:
                    raise ValueError('hub_has_another_owner')
            await network.activate(request.get('ssid'), request.get('password'))
            uid = await asyncio.to_thread(self.hub.cloud.verify_patient, request.get('id_token'))
            existing_hub = await asyncio.to_thread(self.hub.cloud.patient_hub, request.get('id_token'), uid)
            if existing_hub not in (None, self.hub.id):
                raise ValueError('patient_has_another_hub')
            registry = await asyncio.to_thread(self.hub.cloud.get, f'{ROOT}/hubs/{self.hub.id}') or {}
            if (expected and uid != expected) or registry.get('owner_uid') not in (None, uid):
                raise ValueError('hub_has_another_owner')
            # Persist the recovery key before the cloud claim. Retry by the same phone can recover a lost response.
            if not self.config.get('owner_key'):
                self.save(owner_key=owner_key, pending_owner_uid=uid)
            await asyncio.to_thread(self.hub.cloud.request, 'PATCH', ROOT,
                                    {f'hubs/{self.hub.id}/owner_uid': uid, f'patientHub/{uid}': self.hub.id})
            self.save(owner_uid=uid, pending_owner_uid=None)
            self.hub.owner = uid
            self.hub.store.set('owner_uid', uid)
            await network.commit()
            result = {'ok': True, 'code': 'paired', 'hub_id': self.hub.id}
        except Exception as error:
            known = {'session_active', 'invalid_owner_key', 'invalid_ssid', 'invalid_wifi_password',
                     'wifi_connection_failed', 'wifi_connection_timeout', 'hub_has_another_owner', 'patient_has_another_hub',
                     'patient_verification_failed', 'patient_account_required', 'invalid_patient_token'}
            result['code'] = str(error) if isinstance(error, ValueError) and str(error) in known else 'provisioning_failed'
            try:
                await network.rollback()
            except Exception:
                result['code'] = 'wifi_restore_pending'
        finally:
            self.hub.provisioning = False
            try:
                for part in chunks(channel.encrypt(result)):
                    self.response.publish(part)
                    await asyncio.sleep(.03)
            finally:
                self.busy = False
                self.device = None


class GattService(ServiceInterface):
    def __init__(self):
        super().__init__('org.bluez.GattService1')

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's': return SERVICE_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> 'b': return True

    def properties(self):
        return {'UUID': Variant('s', self.UUID), 'Primary': Variant('b', True)}


class Characteristic(ServiceInterface):
    def __init__(self, uuid, flags, provisioner):
        super().__init__('org.bluez.GattCharacteristic1')
        self.uuid, self.flags, self.provisioner = uuid, flags, provisioner
        self.value, self.notifying = b'', False

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's': return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> 'o': return SERVICE

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> 'as': return self.flags

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> 'ay': return self.value

    @dbus_property(access=PropertyAccess.READ)
    def Notifying(self) -> 'b': return self.notifying

    @method()
    def ReadValue(self, options: 'a{sv}') -> 'ay':
        if self.uuid != CHALLENGE_UUID:
            raise DBusError('org.bluez.Error.NotSupported', 'Not readable')
        return self.provisioner.challenge(options)

    @method()
    def WriteValue(self, value: 'ay', options: 'a{sv}'):
        if self.uuid != REQUEST_UUID:
            raise DBusError('org.bluez.Error.NotSupported', 'Not writable')
        self.provisioner.receive(value, options)

    @method()
    def StartNotify(self):
        self.notifying = True
        self.emit_properties_changed({'Notifying': True})

    @method()
    def StopNotify(self):
        self.notifying = False
        self.emit_properties_changed({'Notifying': False})

    def publish(self, value):
        self.value = value
        if self.notifying:
            self.emit_properties_changed({'Value': value})

    def properties(self):
        return {'UUID': Variant('s', self.uuid), 'Service': Variant('o', SERVICE),
                'Flags': Variant('as', self.flags), 'Notifying': Variant('b', self.notifying)}


class ObjectManager(ServiceInterface):
    def __init__(self, objects):
        super().__init__('org.freedesktop.DBus.ObjectManager')
        self.objects = objects

    @method()
    def GetManagedObjects(self) -> 'a{oa{sa{sv}}}':
        return {path: {obj.name: obj.properties()} for path, obj in self.objects.items()}


class Advertisement(ServiceInterface):
    def __init__(self, hub_id):
        super().__init__('org.bluez.LEAdvertisement1')
        self.hub_id = hub_id

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> 's': return 'peripheral'

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> 'as': return [SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> 's': return 'Rehab-' + self.hub_id[-6:]

    @method()
    def Release(self): pass


async def serve(hub, config, path):
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    provisioner = Provisioner(hub, config, path, bus)
    service = GattService()
    chars = [Characteristic(CHALLENGE_UUID, ['read'], provisioner),
             Characteristic(REQUEST_UUID, ['write'], provisioner),
             Characteristic(RESPONSE_UUID, ['notify'], provisioner)]
    provisioner.response = chars[2]
    objects = {SERVICE: service, **{f'{SERVICE}/char{i}': c for i, c in enumerate(chars)}}
    bus.export(BASE, ObjectManager(objects))
    for object_path, obj in objects.items():
        bus.export(object_path, obj)
    bus.export(BASE + '/advertisement', Advertisement(hub.id))
    intro = await bus.introspect(BLUEZ, '/org/bluez/hci0')
    adapter = bus.get_proxy_object(BLUEZ, '/org/bluez/hci0', intro)
    await adapter.get_interface('org.freedesktop.DBus.Properties').call_set('org.bluez.Adapter1', 'Powered', Variant('b', True))
    await adapter.get_interface('org.bluez.GattManager1').call_register_application(BASE, {})
    await adapter.get_interface('org.bluez.LEAdvertisingManager1').call_register_advertisement(BASE + '/advertisement', {})
    LOG.info('Bluetooth provisioning ready')
    try:
        while not hub.stop.is_set():
            await asyncio.sleep(.5)
    finally:
        bus.disconnect()


def start_ble(hub, config, path):
    def run():
        while not hub.stop.is_set():
            try:
                asyncio.run(serve(hub, config, path))
            except Exception as error:
                LOG.error('Bluetooth unavailable: %s', type(error).__name__)
                hub.stop.wait(10)
    threading.Thread(target=run, name='bluetooth', daemon=True).start()
