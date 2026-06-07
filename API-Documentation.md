# API Documentation

As **fleat** was especially developed to be 'usage compatible' to code using
Bleak, please also check the [Bleak documentation](https://bleak.readthedocs.io/en/latest/index.html).

---

## fleat `FleatScanner`

A class to scan for Bluetooth LE devices on Android via pyjnius. Usage-compatible
with Bleak's `BleakScanner`. Can be used as an asynchronous context manager or
via its class methods for one-shot scans.

```python
# General discovery scan:
devices = await FleatScanner.discover()
for d in devices:
    print(d.address, d.name)

# Find a device by name:
device = await FleatScanner.find_device_by_name('MyDevice')

# Find a device by MAC address:
device = await FleatScanner.find_device_by_address('AA:BB:CC:DD:EE:FF')

# With a live detection callback:
def callback(device, advertising_data):
    print(device.name, device.rssi)

async with FleatScanner(detection_callback=callback) as scanner:
    await asyncio.sleep(5.0)
```

### Properties and methods of `BleakScanner` that are *not* available in fleat's `FleatScanner`

- *discovered_devices_and_advertisement_data* (advertising data is not surfaced)
- *find_device_by_filter()*
- *register_detection_callback()* (use the constructor argument instead)

---

### `FleatScanner` constructor

#### **FleatScanner(*detection_callback=None, \*, scanning_mode="active"*)**

*Class to scan for Bluetooth LE devices.*

- **detection_callback**: An optional callable invoked for each detected device.
  Signature: `callback(device: BLEDevice, advertising_data)`.
  Note: `advertising_data` is always `None` in this implementation — Android's
  advertising data is not currently parsed and forwarded.
- **scanning_mode**: `"active"` or `"passive"` (`str`). Currently informational
  only; Android always uses `SCAN_MODE_LOW_LATENCY` regardless of this setting.

#### Differences to `BleakScanner`

The `scanning_mode` parameter has no effect on the underlying Android scan mode.
`advertising_data` passed to the detection callback is always `None`; Bleak
passes a populated `AdvertisementData` object.

---

### `FleatScanner` properties

#### *discovered_devices*

*Property that holds all BLE devices discovered since scanning started.*

Returns a `list` of `BLEDevice` objects. The list is populated continuously
while scanning is active and is cleared when `start()` is called.

##### Differences to `BleakScanner.discovered_devices`

Bleak additionally provides `discovered_devices_and_advertisement_data` (a
`dict` mapping addresses to `(BLEDevice, AdvertisementData)` tuples). fleat
does not provide advertisement data.

---

### `FleatScanner` methods

#### **start()**

*Async method to start scanning for BLE devices.*

Clears the list of previously discovered devices, starts the Android BLE scan
on a background thread using `BluetoothLeScanner` with `SCAN_MODE_LOW_LATENCY`,
and launches an asyncio task to drain scan results and invoke the detection
callback.

Does nothing if scanning is already active.

Raises `fleatError` (via the event queue) if Bluetooth is not supported,
Bluetooth is not enabled, the BLE scanner is unavailable, or the scan fails
(e.g. `SCAN_FAILED_ALREADY_STARTED`, `SCAN_FAILED_INTERNAL_ERROR`).

---

#### **stop()**

*Async method to stop scanning for BLE devices.*

Signals the background scan thread to stop, calls `stopScan()` on the Android
`BluetoothLeScanner`, and waits up to 3 seconds for the thread to finish.

---

#### **discover(*timeout=5.0, \*, detection_callback=None*)**

*Class method. Perform a BLE scan for* `timeout` *seconds and return all
discovered devices.*

Compatible with `BleakScanner.discover()`.

- **timeout**: Duration in seconds to scan (`float`). Default: `5.0`.
- **detection_callback**: Optional callback called for each device found during
  the scan. Signature: `callback(device: BLEDevice, advertising_data)`.

Returns a `list` of `BLEDevice` objects for all devices discovered within the
timeout period.

---

#### **find_device_by_name(*name, timeout=10.0, \*\*kwargs*)**

*Class method. Scan for a BLE device with the given name and return it as soon
as it is found.*

Compatible with `BleakScanner.find_device_by_name()`.

- **name**: The exact device name to search for (`str`). Case-sensitive.
- **timeout**: Maximum scan duration in seconds (`float`). Default: `10.0`.
- **Additional keyword arguments**: Without function.

Returns a `BLEDevice` if the device was found before the timeout, or `None`
if the scan timed out without finding the device.

##### Differences to `BleakScanner.find_device_by_name()`

Matching is case-sensitive and requires an exact name match. Bleak additionally
supports a `cb` keyword argument for a custom callback predicate.

---

#### **find_device_by_address(*device_identifier, timeout=10.0, \*\*kwargs*)**

*Class method. Scan for a BLE device with the given MAC address and return it
as soon as it is found.*

Compatible with `BleakScanner.find_device_by_address()`.

- **device_identifier**: The MAC address string (`str`), e.g.
  `'AA:BB:CC:DD:EE:FF'`. Matching is case-insensitive.
- **timeout**: Maximum scan duration in seconds (`float`). Default: `10.0`.
- **Additional keyword arguments**: Without function.

Returns a `BLEDevice` if the device was found before the timeout, or `None`
if the scan timed out without finding the device.

This method is also used internally by `FleatClient.connect()` when initialised
with a MAC address string instead of a `BLEDevice` object.

---

## fleat `FleatClient`

A class to connect to and communicate with a BLE GATT server (a BLE peripheral)
on Android via pyjnius. Like Bleak's `BleakClient`, you can use `FleatClient` as
an asynchronous context manager or manually connect and disconnect.

```python
# As an async context manager:
async with FleatClient(device) as client:
    await client.start_notify(NOTIFY_UUID, my_callback)
    await asyncio.sleep(10)

# Or manually:
client = FleatClient(device)
await client.connect()
data = await client.read_gatt_char(READ_UUID)
await client.disconnect()
```

### Properties and methods of `BleakClient` that are *not* available in fleat's `FleatClient`

- *read_gatt_descriptor()*
- *write_gatt_descriptor()*
- *pair()*
- *unpair()* (there is no *unpair* functionality in Android anyway)
- *set_disconnected_callback()* (deprecated in Bleak)

---

### `FleatClient` constructor

#### **FleatClient(*address_or_ble_device, disconnected_callback=None, \*\*kwargs*)**

*Class to connect to a Bluetooth LE GATT server (a BLE device) and communicate with it.*

- **address_or_ble_device**: A `BLEDevice` object or a MAC address string (`str`).
  If a MAC address string is provided, a BLE scan will be performed automatically
  during `connect()` to retrieve the native `BluetoothDevice` object.
- **disconnected_callback**: An optional synchronous callback invoked when the
  client is disconnected. Signature: `callback(client: FleatClient)`.
- **Additional keyword arguments**: Without function.

#### Differences to `BleakClient`

Unlike `BleakClient`, `FleatClient` *will* actively scan for the device if only a
MAC address string is given (the scan happens inside `connect()`, not in the
constructor). Additional keyword arguments are not handled.

---

### `FleatClient` properties

#### *address*

*Property that holds the MAC address of the BLE device.*

Returns a `str`.

#### *is_connected*

*Property indicating the current connection status.*

Returns `True` if currently connected to the BLE device, `False` otherwise.

#### *mtu_size*

*Property that holds the negotiated MTU size for this connection.*

During connection, `FleatClient` automatically requests the maximum MTU (517).
The actually negotiated value depends on the peripheral and Android stack.

Returns an `int`. Default before negotiation is `23`.

#### *services*

*Property that holds the GATT services discovered on the connected device.*

Returns a `list` of `BLEGattService` objects. Each `BLEGattService` object has
the following attributes:

- **uuid** (`str`): The service UUID as a string.
- **service**: The native Android `BluetoothGattService` Java object.
- **characteristics** (`list[str]`): List of characteristic UUID strings belonging
  to this service.

Services are populated automatically after a successful connection (service
discovery runs as part of `connect()`).

##### Differences to `BleakClient.services`

This is a notable difference to Bleak. Bleak returns a `BLEGattServiceCollection`.
fleat returns a plain `list` of `BLEGattService` objects. fleat's `BLEGattService`
objects are also different from Bleak's — they expose the native Android GATT
service object and a flat list of characteristic UUID strings, but do not contain
descriptor data.

---

### `FleatClient` methods

#### **connect(*timeout=10.0, \*\*kwargs*)**

*Async method to connect the client to the BLE device and discover its services.*

- **timeout**: Maximum time in seconds to wait for connection and service
  discovery (`float`). Default: `10.0`.
- **Additional keyword arguments**: Without function.

Returns `True` if the connection and service discovery were successful.

Raises `fleatError` if the device is not found, the connection times out,
the connection fails, or service discovery times out.

If `FleatClient` was initialised with a MAC address string, a BLE scan is
performed first (using `FleatScanner.find_device_by_address()`) before the
GATT connection is established.

MTU negotiation (requesting MTU 517) is performed automatically after service
discovery. The `connect()` call returns only after MTU negotiation has
completed or failed.

##### Differences to `BleakClient.connect()`

Additional keyword arguments are not handled. `BleakClient` accepts an optional
*timeout* keyword argument in the constructor; `FleatClient` accepts it here in
`connect()` directly.

---

#### **disconnect()**

*Async method to disconnect the client from the BLE device.*

Returns `True` once the disconnect sequence has completed (or timed out after
5 seconds). Closes the underlying GATT connection and stops the internal event
processing task.

---

#### **read_gatt_char(*char_specifier, \*\*kwargs*)**

*Async method to read the value of a GATT characteristic.*

- **char_specifier**: The characteristic UUID as a string (`str`).
- **Additional keyword arguments**: Without function.

Returns the characteristic value as `bytes`.

Raises `fleatError` if not connected, the characteristic is not found, the
underlying `readCharacteristic` call returns `False`, or the read times out
(default timeout: 10 seconds).

##### Differences to `BleakClient.read_gatt_char()`

The characteristic *must* be identified by its UUID string. Identifying
characteristics by index or `BLEGattCharacteristic` object is not supported.

---

#### **write_gatt_char(*char_specifier, data, response=False, \*\*kwargs*)**

*Async method to write data to a GATT characteristic.*

- **char_specifier**: The characteristic UUID as a string (`str`).
- **data**: The data to write (`bytes` or `bytearray`).
- **response**: If `True`, uses `WRITE_TYPE_DEFAULT` (write with response) and
  awaits the write confirmation from the peripheral. If `False` (default), uses
  `WRITE_TYPE_NO_RESPONSE` and returns immediately after issuing the write.
- **Additional keyword arguments**: Without function.

Returns `None`.

Raises `fleatError` if not connected, the characteristic is not found, the
underlying `writeCharacteristic` call returns `False`, or the write with
response times out (default timeout: 10 seconds).

##### Differences to `BleakClient.write_gatt_char()`

The characteristic *must* be identified by its UUID string. Unlike Bleak,
there is no automatic detection of the write type based on characteristic
properties — the **response** flag must be set explicitly by the caller.

---

#### **start_notify(*char_specifier, callback, \*\*kwargs*)**

*Async method to subscribe to notifications from a GATT characteristic.*

- **char_specifier**: The characteristic UUID as a string (`str`).
- **callback**: A regular or async callable invoked when a notification arrives.
  Signature: `callback(uuid: str, data: bytes)`.
- **Additional keyword arguments**: Without function.

Enables local notifications on the GATT client via
`setCharacteristicNotification()` and writes `ENABLE_NOTIFICATION_VALUE` to
the Client Characteristic Configuration Descriptor (CCCD, UUID
`00002902-0000-1000-8000-00805f9b34fb`) to instruct the peripheral to start
sending notifications. If the CCCD is absent or the descriptor write times out,
the method continues without raising an error.

Raises `fleatError` if not connected, the characteristic is not found, or
`setCharacteristicNotification()` fails.

##### Differences to `BleakClient.start_notify()`

The characteristic *must* be identified by its UUID string.

The callback signature differs from Bleak's: Bleak passes
`(BLEGattCharacteristic, bytearray)`, while fleat passes `(uuid_str, bytes)`
for cross-platform simplicity.

Indications (notifications requiring client acknowledgement) are not supported.

---

#### **stop_notify(*char_specifier, \*\*kwargs*)**

*Async method to unsubscribe from notifications for a GATT characteristic.*

- **char_specifier**: The characteristic UUID as a string (`str`).
- **Additional keyword arguments**: Without function.

Disables notifications via `setCharacteristicNotification(..., False)` and
writes `DISABLE_NOTIFICATION_VALUE` to the CCCD to inform the peripheral.
Removes the registered Python callback.

Raises `fleatError` if not connected or the characteristic is not found.

##### Differences to `BleakClient.stop_notify()`

The characteristic *must* be identified by its UUID string.

---

#### **get_services()**

*Async method to return the list of discovered GATT services.*

Returns the same `list` of `BLEGattService` objects as the `services` property.
Provided for compatibility with deprecated usage patterns in Bleak.

##### Differences to `BleakClient.get_services()`

Bleak's `get_services()` is deprecated and returns a `BLEGattServiceCollection`.
fleat's implementation returns a plain `list` of `BLEGattService` objects (see
the `services` property for details). This method performs no additional
discovery — it simply returns the services already populated during `connect()`.

---

## fleat `BLEGattService`

Represents a GATT service discovered on a connected BLE device.

> **Note:** This class is different from Bleak's `BLEGattService`.

### `BLEGattService` attributes

#### *uuid*

The service UUID as a lowercase string (`str`), e.g.
`"0000180a-0000-1000-8000-00805f9b34fb"`.

#### *service*

The native Android `BluetoothGattService` Java object. Can be used to call
Android GATT APIs directly when needed.

#### *characteristics*

A `list` of characteristic UUID strings (`list[str]`) belonging to this service.
Descriptor data is not included.

---

## fleat `BLEDevice`

A data class representing a discovered Bluetooth LE device. Compatible with
Bleak's `BLEDevice`.

`BLEDevice` objects are created internally by `FleatScanner` and returned by
`discover()`, `find_device_by_name()`, and `find_device_by_address()`. They
can also be passed directly to the `FleatClient` constructor.

### `BLEDevice` properties

#### *address*

The MAC address of the BLE device as a string (`str`),
e.g. `"AA:BB:CC:DD:EE:FF"`.

#### *name*

The advertised name of the BLE device (`str`), or `None` if the device did
not advertise a name at the time of discovery.

#### *details*

The native Android `BluetoothDevice` Java object (pyjnius). Required by
`FleatClient` to establish a GATT connection. Direct use of this object
is only necessary when calling Android GATT APIs not covered by fleat.

##### Differences to `BleakClient.details`

Bleak's `details` attribute holds a platform-specific object that varies by
OS (e.g. a Core Bluetooth peripheral on macOS). In fleat, it is always the
Android `BluetoothDevice` Java object.

#### *rssi*

The received signal strength indicator at the time of discovery (`int`),
in dBm. A value of `0` indicates that no RSSI was available.

##### Differences to `BleakClient.rssi`

In Bleak, `rssi` is not a property of `BLEDevice` itself but is part of
`AdvertisementData`. fleat attaches it directly to `BLEDevice` for convenience,
since advertisement data is not otherwise surfaced.
