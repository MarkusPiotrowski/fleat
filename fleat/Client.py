"""
FleatClient - BLE GATT client for Flet on Android via pyjnius.

Provides connect/disconnect, notification subscription, and read/write
functionality compatible with Bleak's BleakClient.

"""

import asyncio
import threading
from queue import Queue, Empty

from fleat.BLEDevice import BLEDevice
from fleat import (
    _fix_class_loader,
    _get_activity,
    check_for_permissions,
    fleatError,
)

from jnius import autoclass, PythonJavaClass, java_method


# Load the Java classes
BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
BluetoothGattCharacteristic = autoclass(
    'android.bluetooth.BluetoothGattCharacteristic'
)
BluetoothGattDescriptor = autoclass(
    'android.bluetooth.BluetoothGattDescriptor'
)
UUID = autoclass('java.util.UUID')

# GATT status code for success
GATT_SUCCESS = 0
# Client Characteristic Configuration Descriptor
CCCD_UUID = '00002902-0000-1000-8000-00805f9b34fb'


class _GattEvent:
    """Internal event types passed through the GATT event queue."""

    CONNECTION_STATE = 'connection_state'
    SERVICES_DISCOVERED = 'services_discovered'
    CHAR_READ = 'char_read'
    CHAR_WRITE = 'char_write'
    DESCRIPTOR_WRITE = 'descriptor_write'
    CHAR_CHANGED = 'char_changed'
    MTU_CHANGED = 'mtu_changed'
    ERROR = 'error'


class BLEGattService:
    """Represents a GATT service discovered on a connected BLE device.

    Attributes:
        uuid (str): The service UUID as a string.
        service: The native Android BluetoothGattService Java object.
        characteristics (list[str]): List of characteristic UUID strings.
    """

    def __init__(self, uuid, service, characteristics):
        self.uuid = uuid
        self.service = service
        self.characteristics = characteristics

    def __repr__(self):
        return (
            f'BLEGattService(uuid={self.uuid}, '
            f'characteristics={self.characteristics})'
        )


class FleatClient:
    """A client for connecting to and communicating with a BLE GATT server.

    Usage-compatible with Bleak's BleakClient.

    Can be used as an async context manager::

        async with FleatClient(device) as client:
            await client.start_notify(NOTIFY_UUID, my_callback)
            await asyncio.sleep(10)

    Or manually::

        client = FleatClient(device)
        await client.connect()
        data = await client.read_gatt_char(READ_UUID)
        await client.disconnect()

    Args:
        address_or_ble_device: A BLEDevice object or a MAC address string.
            Note: If a MAC address string is given, a BLE scan will be
            performed first to retrieve the native BluetoothDevice object.
        disconnected_callback: Optional synchronous callback called on
            disconnection. Signature: callback(client: FleatClient).
    """

    def __init__(
        self,
        address_or_ble_device,
        disconnected_callback=None,
        **kwargs,
    ):
        if isinstance(address_or_ble_device, BLEDevice):
            self._device = address_or_ble_device
            self._address = address_or_ble_device.address
        else:
            self._device = None
            self._address = address_or_ble_device

        self._disconnected_callback = disconnected_callback
        self._gatt = None
        self._gatt_queue = Queue()
        self._is_connected = False
        self._services = []
        self._notify_callbacks = {}
        self._gatt_thread = None
        self._event_task = None
        self._loop = None

        # Per-operation events and results
        self._connect_event = asyncio.Event()
        self._disconnect_event = asyncio.Event()
        self._services_event = asyncio.Event()
        self._char_read_event = asyncio.Event()
        self._char_write_event = asyncio.Event()
        self._descriptor_write_event = asyncio.Event()
        self._mtu_event = asyncio.Event()

        self._char_read_result = None
        self._last_status = GATT_SUCCESS
        self._mtu = 23  # Default BLE MTU

    # --- Async context manager support ---

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False

    # --- Properties ---

    @property
    def address(self) -> str:
        """The MAC address of the connected BLE device."""
        return self._address

    @property
    def is_connected(self) -> bool:
        """True if currently connected to the BLE device."""
        return self._is_connected

    @property
    def services(self) -> list[BLEGattService]:
        """List of BLEGattService objects discovered on the connected device.

        Note: Unlike Bleak which returns a BLEGattServiceCollection,
        fleat returns a plain list of BLEGattService objects.
        Services are populated after a successful connection.
        """
        return self._services

    @property
    def mtu_size(self) -> int:
        """The negotiated MTU size for this connection."""
        return self._mtu

    # --- Connection ---

    async def connect(self, timeout=10.0, **kwargs):
        """Connect to the BLE device.

        If initialized with a MAC address string (not a BLEDevice), a scan
        is performed first to get the native BluetoothDevice object.

        Args:
            timeout: Connection timeout in seconds.

        Returns:
            True if connected successfully.

        Raises:
            fleatError: If connection fails or times out.
        """
        self._loop = asyncio.get_event_loop()

        check_for_permissions()

        # If we only have an address string, scan for the device first:
        if self._device is None:
            from fleat.Scanner import FleatScanner

            self._device = await FleatScanner.find_device_by_address(
                self._address, timeout=timeout
            )
            if self._device is None:
                raise fleatError(
                    f'Device with address {self._address} '
                    'not found during scan.'
                )

        self._connect_event.clear()
        self._services_event.clear()

        # Start the event processing task.
        self._event_task = self._loop.create_task(self._process_gatt_events())

        # Connect on a background thread
        # (GATT operations must not block the main thread).
        thread = threading.Thread(target=self._connect_thread, daemon=True)
        thread.start()

        # Wait for connection.
        try:
            await asyncio.wait_for(self._connect_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise fleatError(
                f'Connection to {self._address} timed out after {timeout}s.'
            )

        if not self._is_connected:
            raise fleatError(
                f'Connection to {self._address} failed '
                f'(status={self._last_status}).'
            )

        # Wait for service discovery.
        try:
            await asyncio.wait_for(
                self._services_event.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            raise fleatError('Service discovery timed out.')

        return True

    def _connect_thread(self):
        """Run the Android GATT connection on a background thread.

        Set up the GattCallback proxy and initiates connection.
        """
        try:
            # FleatGattCallback is a user Java class and requires the class
            # loader of the app to be loaded:
            _fix_class_loader()

            from jnius import autoclass

            FleatGattCallback = autoclass('com.fleat.ble.FleatGattCallback')

            # PyGattCallback implements FleatGattCallback$Interface –
            # a true Java interface that can be handled by das pyjnius.
            # FleatGattCallback (Java) extends BluetoothGattCallback and
            # delegates to this interface.
            class PyGattCallback(PythonJavaClass):
                __javainterfaces__ = [
                    'com/fleat/ble/FleatGattCallback$Interface'
                ]
                __javacontext__ = 'app'

                def __init__(self, client):
                    super().__init__()
                    self.client = client  # reference to client

                @java_method('(II)V')
                def onConnectionStateChange(self, status, newState):
                    self.client._gatt_queue.put(
                        (_GattEvent.CONNECTION_STATE, status, newState)
                    )

                @java_method('(I)V')
                def onServicesDiscovered(self, status):
                    self.client._gatt_queue.put(
                        (_GattEvent.SERVICES_DISCOVERED, status)
                    )

                @java_method('(Ljava/lang/String;[BI)V')
                def onCharacteristicRead(self, uuid, value, status):
                    # value is jnius.ByteString, convert to Python bytestring:
                    value = value.tostring() if value else b''
                    self.client._gatt_queue.put(
                        (_GattEvent.CHAR_READ, uuid, value, status)
                    )

                @java_method('(Ljava/lang/String;I)V')
                def onCharacteristicWrite(self, uuid, status):
                    self.client._gatt_queue.put(
                        (_GattEvent.CHAR_WRITE, uuid, status)
                    )

                @java_method('(Ljava/lang/String;I)V')
                def onDescriptorWrite(self, uuid, status):
                    self.client._gatt_queue.put(
                        (_GattEvent.DESCRIPTOR_WRITE, uuid, status)
                    )

                @java_method('(Ljava/lang/String;[B)V')
                def onCharacteristicChanged(self, uuid, value):
                    # value is jnius.ByteString, convert to Python bytestring:
                    value = value.tostring() if value else b''
                    self.client._gatt_queue.put(
                        (_GattEvent.CHAR_CHANGED, uuid, value)
                    )

                @java_method('(II)V')
                def onMtuChanged(self, mtu, status):
                    self.client._gatt_queue.put(
                        (_GattEvent.MTU_CHANGED, mtu, status)
                    )

            try:
                context = _get_activity()
            except fleatError:
                # Fallback: app context sufficient for connectGatt()
                context = autoclass(
                    'android.app.ActivityThread'
                ).currentApplication()

            self._p_callback = PyGattCallback(self)
            # FleatGattCallback() initiates the Java bridge
            self._callback_ref = FleatGattCallback(self._p_callback)
            native_device = self._device.details

            self._gatt = native_device.connectGatt(
                context, False, self._callback_ref
            )

            # Request for higher MTU for better throughput is done after
            # connection and service discovery is established (see
            # onServicesDiscovered).

        except Exception as e:
            self._gatt_queue.put(
                (_GattEvent.ERROR, fleatError(f"Connect thread error: {e}"))
            )

    async def _process_gatt_events(self):
        """Process the events in the GATT event queue.

        Async task that drains the GATT event queue and resolves pending
        operations.
        """
        while True:
            try:
                item = self._gatt_queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.02)
                continue

            if item is None:
                break

            event_type = item[0]

            if event_type == _GattEvent.CONNECTION_STATE:
                _, status, new_state = item
                self._last_status = status
                if new_state == 2 and status == GATT_SUCCESS:
                    self._is_connected = True
                    self._gatt.discoverServices()
                    self._connect_event.set()
                else:
                    self._is_connected = False
                    self._connect_event.set()
                    if self._disconnected_callback:
                        try:
                            self._disconnected_callback(self)
                        except Exception:
                            pass
                    # Signal any awaiting operations.
                    self._disconnect_event.set()
                    break

            elif event_type == _GattEvent.SERVICES_DISCOVERED:
                _, status = item
                if status == GATT_SUCCESS:
                    self._services = self._parse_services(self._gatt)
                # now we try to raise the MTU:
                try:
                    self._mtu_event.clear()
                    self._gatt.requestMtu(517)
                except Exception:
                    self._services_event.set()

            elif event_type == _GattEvent.CHAR_READ:
                _, uuid, value, status = item
                self._last_status = status
                self._char_read_result = (
                    value if status == GATT_SUCCESS else None
                )
                self._char_read_event.set()

            elif event_type == _GattEvent.CHAR_WRITE:
                _, uuid, status = item
                self._last_status = status
                self._char_write_event.set()

            elif event_type == _GattEvent.DESCRIPTOR_WRITE:
                _, uuid, status = item
                self._last_status = status
                self._descriptor_write_event.set()

            elif event_type == _GattEvent.CHAR_CHANGED:
                _, uuid, value = item
                callback = self._notify_callbacks.get(uuid.lower())
                if callback:
                    try:
                        result = callback(uuid, value)
                        if asyncio.iscoroutine(result):
                            asyncio.create_task(result)
                    except Exception:
                        pass

            elif event_type == _GattEvent.MTU_CHANGED:
                _, mtu, status = item
                if status == GATT_SUCCESS:
                    self._mtu = mtu
                self._mtu_event.set()
                self._services_event.set()

            elif event_type == _GattEvent.ERROR:
                raise item[1]

    def _parse_services(self, gatt):
        """Parse the discovered services from a connected GATT object."""
        result = []
        try:
            services = gatt.getServices()
            for i in range(services.size()):
                service = services.get(i)
                uuid_str = service.getUuid().toString()
                char_uuids = []
                chars = service.getCharacteristics()
                for j in range(chars.size()):
                    char_uuids.append(chars.get(j).getUuid().toString())
                result.append(
                    BLEGattService(
                        uuid=uuid_str,
                        service=service,
                        characteristics=char_uuids,
                    )
                )
        except Exception:
            pass
        return result

    # --- Disconnection ---

    async def disconnect(self):
        """Disconnect from the BLE device."""
        if self._gatt is not None:
            self._disconnect_event.clear()
            try:
                self._gatt.disconnect()
                await asyncio.wait_for(
                    self._disconnect_event.wait(), timeout=5.0
                )
            except asyncio.TimeoutError:
                pass
            try:
                self._gatt.close()
            except Exception:
                pass
            self._gatt = None

        self._is_connected = False

        if self._event_task and not self._event_task.done():
            self._gatt_queue.put(None)  # Sentinel to end the event loop task.
            self._event_task.cancel()

        return True

    # --- GATT read/write/notify ---

    def _find_characteristic(self, uuid):
        """Find a characteristic by UUID across all discovered services.

        Args:
            uuid: The characteristic UUID string (128-bit format).

        Returns:
            The native BluetoothGattCharacteristic Java object.

        Raises:
            fleatError: If the characteristic is not found.
        """
        if len(uuid) == 4:
            uuid = f'0000{uuid}-0000-1000-8000-00805f9b34fb'
        elif len(uuid) == 8:
            uuid = f'{uuid}-0000-1000-8000-00805f9b34fb'
        uuid_lower = uuid.lower()

        for service in self._services:
            if uuid_lower in service.characteristics:
                return service.service.getCharacteristic(
                    UUID.fromString(uuid_lower)
                )
        raise fleatError(
            f'Characteristic {uuid} not found on connected device.'
        )

    async def read_gatt_char(self, char_specifier, **kwargs):
        """Read the value of a GATT characteristic.

        Compatible with BleakClient.read_gatt_char().

        Args:
            char_specifier: The characteristic's UUID string.

        Returns:
            The characteristic value as bytes.

        Raises:
            fleatError: If not connected, characteristic not found,
            or read fails.
        """
        if not self._is_connected or self._gatt is None:
            raise fleatError('Not connected to a BLE device.')

        characteristic = self._find_characteristic(char_specifier)
        self._char_read_event.clear()
        self._char_read_result = None

        success = self._gatt.readCharacteristic(characteristic)
        if not success:
            raise fleatError(
                f'readCharacteristic returned false for {char_specifier}.'
            )

        try:
            await asyncio.wait_for(self._char_read_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise fleatError(
                f'Read of characteristic {char_specifier} timed out.'
            )

        if self._char_read_result is None:
            raise fleatError(
                f'Read of characteristic {char_specifier} failed '
                f'(status={self._last_status}).'
            )

        return self._char_read_result

    async def write_gatt_char(
        self,
        char_specifier,
        data,
        response=False,
        **kwargs,
    ):
        """Write data to a GATT characteristic.

        Compatible with BleakClient.write_gatt_char().

        Args:
            char_specifier: The characteristic UUID string.
            data: The data to write as bytes or bytearray.
            response: If True, use WRITE_TYPE_DEFAULT (with response).
                      If False, use WRITE_TYPE_NO_RESPONSE. Default is False.

        Raises:
            fleatError: If not connected, characteristic not found, or write
            fails.
        """
        if not self._is_connected or self._gatt is None:
            raise fleatError('Not connected to a BLE device.')

        characteristic = self._find_characteristic(char_specifier)

        if response:
            write_type = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        else:
            write_type = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE

        characteristic.setWriteType(write_type)
        characteristic.setValue(bytes(data))

        self._char_write_event.clear()

        success = self._gatt.writeCharacteristic(characteristic)
        if not success:
            raise fleatError(
                f'writeCharacteristic returned false for {char_specifier}.'
            )

        if response:
            try:
                await asyncio.wait_for(
                    self._char_write_event.wait(), timeout=10.0
                )
            except asyncio.TimeoutError:
                raise fleatError(
                    f'Write to characteristic {char_specifier} timed out.'
                )

            if self._last_status != GATT_SUCCESS:
                raise fleatError(
                    f'Write to characteristic {char_specifier} failed '
                    f'(status={self._last_status}).'
                )

    async def start_notify(self, char_specifier, callback, **kwargs):
        """Subscribe to notifications for a GATT characteristic.

        Compatible with BleakClient.start_notify().

        The callback receives (uuid_string, data_bytes) when a notification
        arrives. Note: Bleak passes (BLEGattCharacteristic, data) but fleat
        passes (uuid_str, data) for simplicity.

        Args:
            char_specifier: The characteristic UUID string.
            callback: Callable with signature callback(uuid: str, data: bytes).
                      Can be a regular function or an async function.

        Raises:
            fleatError: If not connected, characteristic not found, or
                        enabling notifications fails.
        """
        if not self._is_connected or self._gatt is None:
            raise fleatError('Not connected to a BLE device.')

        characteristic = self._find_characteristic(char_specifier)

        # Enable local notifications on the GATT client.
        success = self._gatt.setCharacteristicNotification(
            characteristic, True
        )
        if not success:
            raise fleatError(
                f'setCharacteristicNotification failed for {char_specifier}.'
            )

        descriptor = characteristic.getDescriptor(UUID.fromString(CCCD_UUID))
        if descriptor is not None:
            descriptor.setValue(
                BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            )
            self._descriptor_write_event.clear()
            self._gatt.writeDescriptor(descriptor)
            try:
                await asyncio.wait_for(
                    self._descriptor_write_event.wait(), timeout=5.0
                )
            # Continue even if CCCD write times out; device may not need it.
            except asyncio.TimeoutError:
                pass

        # Register the Python callback.
        self._notify_callbacks[char_specifier.lower()] = callback

    async def stop_notify(self, char_specifier, **kwargs):
        """Unsubscribe from notifications for a GATT characteristic.

        Compatible with BleakClient.stop_notify().

        Args:
            char_specifier: The characteristic UUID string.

        Raises:
            fleatError: If not connected or characteristic not found.
        """
        if not self._is_connected or self._gatt is None:
            raise fleatError('Not connected to a BLE device.')

        characteristic = self._find_characteristic(char_specifier)
        self._gatt.setCharacteristicNotification(characteristic, False)

        descriptor = characteristic.getDescriptor(UUID.fromString(CCCD_UUID))
        if descriptor is not None:
            descriptor.setValue(
                BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE
            )
            self._descriptor_write_event.clear()
            self._gatt.writeDescriptor(descriptor)
            try:
                await asyncio.wait_for(
                    self._descriptor_write_event.wait(), timeout=5.0
                )
            except asyncio.TimeoutError:
                pass

        self._notify_callbacks.pop(char_specifier.lower(), None)

    async def get_services(self):
        """Return the list of GATT services.

        Note: Unlike Bleak which returns a BLEGattServiceCollection,
        fleat returns a plain list of BLEGattService objects.

        Returns:
            List of BLEGattService objects.
        """
        return self._services
