"""Transactional Wi-Fi change over NetworkManager D-Bus; old profile is retained."""
import asyncio
import uuid
from dbus_fast import Variant

BUS = 'org.freedesktop.NetworkManager'
PATH = '/org/freedesktop/NetworkManager'


async def interface(bus, path, name):
    intro = await bus.introspect(BUS, path)
    return bus.get_proxy_object(BUS, path, intro).get_interface(name)


class NetworkChange:
    def __init__(self, bus):
        self.bus, self.profile, self.old_profile, self.device = bus, None, None, None

    async def activate(self, ssid, password):
        if not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32:
            raise ValueError('invalid_ssid')
        if not isinstance(password, str) or (password and not 8 <= len(password) <= 63):
            raise ValueError('invalid_wifi_password')
        manager = await interface(self.bus, PATH, BUS)
        self.device = await manager.call_get_device_by_ip_iface('wlan0')
        props = await interface(self.bus, self.device, 'org.freedesktop.DBus.Properties')
        current = (await props.call_get(BUS + '.Device', 'ActiveConnection')).value
        if current != '/':
            active = await interface(self.bus, current, 'org.freedesktop.DBus.Properties')
            self.old_profile = (await active.call_get(BUS + '.Connection.Active', 'Connection')).value
        identifier = str(uuid.uuid4())
        connection = {
            'connection': {'id': Variant('s', 'SMART REHAB ' + identifier[:8]),
                           'uuid': Variant('s', identifier), 'type': Variant('s', '802-11-wireless'),
                           'autoconnect': Variant('b', False)},
            '802-11-wireless': {'ssid': Variant('ay', ssid.encode()), 'mode': Variant('s', 'infrastructure')},
            'ipv4': {'method': Variant('s', 'auto')}, 'ipv6': {'method': Variant('s', 'auto')},
        }
        if password:
            connection['802-11-wireless-security'] = {'key-mgmt': Variant('s', 'wpa-psk'), 'psk': Variant('s', password)}
        settings = await interface(self.bus, PATH + '/Settings', BUS + '.Settings')
        self.profile = await settings.call_add_connection(connection)
        self.settings = connection
        try:
            await manager.call_activate_connection(self.profile, self.device, '/')
            for _ in range(90):
                state = (await props.call_get(BUS + '.Device', 'State')).value
                active_path = (await props.call_get(BUS + '.Device', 'ActiveConnection')).value
                if state == 100 and active_path != '/':
                    active = await interface(self.bus, active_path, 'org.freedesktop.DBus.Properties')
                    used = (await active.call_get(BUS + '.Connection.Active', 'Connection')).value
                    if used == self.profile:
                        return
                if state in (120, 20):
                    raise ValueError('wifi_connection_failed')
                await asyncio.sleep(.5)
            raise ValueError('wifi_connection_timeout')
        except Exception:
            await self.rollback()
            raise ValueError('wifi_connection_failed') from None

    async def commit(self):
        if self.profile:
            self.settings['connection']['autoconnect'] = Variant('b', True)
            self.settings['connection']['autoconnect-priority'] = Variant('i', 100)
            profile = await interface(self.bus, self.profile, BUS + '.Settings.Connection')
            await profile.call_update(self.settings)

    async def rollback(self):
        if not self.profile:
            return
        manager = await interface(self.bus, PATH, BUS)
        if self.old_profile:
            await manager.call_activate_connection(self.old_profile, self.device, '/')
        # Delete only the temporary profile created by this failed transaction.
        profile = await interface(self.bus, self.profile, BUS + '.Settings.Connection')
        await profile.call_delete()
        self.profile = None
