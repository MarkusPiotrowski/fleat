"""
FleatScanner - BLE scanner for Flet on Android via pyjnius.

Provides scanning functionality compatible with Bleak's BleakScanner.
Supports scanning by name, by MAC address, and general discovery scans.

"""

import asyncio
import threading
import time
from queue import Queue, Empty

from fleat.BLEDevice import BLEDevice
from fleat import fleatError, check_for_permissions, _fix_class_loader

from jnius import autoclass, PythonJavaClass, java_method


# Load the required Java classes
BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
ScanSettings = autoclass('android.bluetooth.le.ScanSettings')
ScanSettingsBuilder = autoclass('android.bluetooth.le.ScanSettings$Builder')


class FleatScanner:
    """Scans for Bluetooth LE devices.

    Usage-compatible with Bleak's BleakScanner. Can be used as a context
    manager (async with) or via its class methods.

    Example (general scan)::

        devices = await FleatScanner.discover()
        for d in devices:
            print(d.address, d.name)

    Example (find by name)::

        device = await FleatScanner.find_device_by_name('MyDevice')

    Example (find by address)::

        device = await FleatScanner.find_device_by_address('AA:BB:CC:DD:EE:FF')

    Example (with detection callback)::

        def callback(device, advertising_data):
            print(device.name, device.rssi)

        async with FleatScanner(detection_callback=callback) as scanner:
            await asyncio.sleep(5.0)
    """

    def __init__(self, detection_callback=None, *, scanning_mode='active'):
        """Initialize a FleatScanner.

        Args:
            detection_callback: A callable that is called for each detected
                device. Signature: callback(device, advertising_data).
                Note: advertising_data is currently None (not available via
                this API layer without additional work).
            scanning_mode: 'active' or 'passive'. Currently informational only;
                Android's default scan mode is used.
        """
        self._detection_callback = detection_callback
        self._scanning_mode = scanning_mode
        self._scan_queue = Queue()
        self._scanning = False
        self._scan_thread = None
        self._found_devices = {}

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
        return False

    async def start(self):
        """Start scanning for BLE devices."""
        if self._scanning:
            return

        check_for_permissions()

        self._found_devices.clear()
        self._scanning = True

        self._scan_thread = threading.Thread(
            target=self._run_scan_thread, daemon=True
        )
        self._scan_thread.start()

        asyncio.get_event_loop().create_task(self._process_scan_results())

    async def stop(self):
        """Stop scanning for BLE devices."""
        self._scanning = False
        self._scan_queue.put(None)
        if self._scan_thread:
            self._scan_thread.join(timeout=3.0)
            self._scan_thread = None

    @property
    def discovered_devices(self):
        """List of all BLEDevice objects discovered since scanning started."""
        return list(self._found_devices.values())

    def _run_scan_thread(self):
        """Run the Android BLE scan on a dedicated thread.

        Uses BluetoothLeScanner with a ScanCallback proxy. Because
        ScanCallback is abstract (not an interface), we implement it
        via pyjnius's java_method reflection on the concrete subclass
        via a Handler-posted queue approach.
        """
        try:
            # FleatScanCallback is a user Java class and requires the class
            # loader of the app to be loaded:
            _fix_class_loader()

            from jnius import autoclass

            FleatScanCallback = autoclass('com.fleat.ble.FleatScanCallback')

            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                self._scan_queue.put(
                    (
                        'error',
                        fleatError('Bluetooth not supported on this device'),
                    )
                )
                return
            if not adapter.isEnabled():
                self._scan_queue.put(
                    ('error', fleatError('Bluetooth is not enabled'))
                )
                return

            ble_scanner = adapter.getBluetoothLeScanner()
            if ble_scanner is None:
                self._scan_queue.put(
                    (
                        'error',
                        fleatError(
                            'BLE scanner not available (Bluetooth may be off)'
                        ),
                    )
                )
                return

            scan_queue = self._scan_queue

            # PyScanCallback implements FleatScanCallback$Interface –
            # a true Java interface, that can be handled by pyjnius.
            # FleatScanCallback (Java) extends ScanCallback und delegates
            # to this interface. This solves the problem of the abstract
            # Java class.
            class PyScanCallback(PythonJavaClass):
                __javainterfaces__ = [
                    'com/fleat/ble/FleatScanCallback$Interface'
                ]
                __javacontext__ = 'app'

                @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
                def onScanResult(self, callbackType, result):
                    try:
                        device = result.getDevice()
                        rssi = result.getRssi()
                        name = device.getName()
                        address = device.getAddress()
                        scan_queue.put(('device', address, name, rssi, device))
                    except Exception as e:
                        scan_queue.put(
                            ('error', fleatError(f'Scan result error: {e}'))
                        )

                @java_method('(Ljava/util/List;)V')
                def onBatchScanResults(self, results):
                    pass

                @java_method('(I)V')
                def onScanFailed(self, errorCode):
                    error_messages = {
                        1: 'SCAN_FAILED_ALREADY_STARTED',
                        2: 'SCAN_FAILED_APPLICATION_REGISTRATION_FAILED',
                        3: 'SCAN_FAILED_INTERNAL_ERROR',
                        4: 'SCAN_FAILED_FEATURE_UNSUPPORTED',
                        5: 'SCAN_FAILED_OUT_OF_HARDWARE_RESOURCES',
                        6: 'SCAN_FAILED_SCANNING_TOO_FREQUENTLY',
                    }
                    msg = error_messages.get(
                        errorCode, f'Unknown error code {errorCode}'
                    )
                    scan_queue.put(
                        ('error', fleatError(f'BLE scan failed: {msg}'))
                    )

            settings = (
                ScanSettingsBuilder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build()
            )

            py_callback = PyScanCallback()
            # FleatScanCallback(py_callback) instantiates the bridge to Java
            self._callback_ref = FleatScanCallback(py_callback)
            ble_scanner.startScan(None, settings, self._callback_ref)
            self._scanner_ref = ble_scanner

            while self._scanning:
                time.sleep(0.1)

            try:
                self._scanner_ref.stopScan(self._callback_ref)
            except Exception:
                pass

        except ImportError:
            self._scan_queue.put(
                (
                    'error',
                    fleatError(
                        'pyjnius is not available. fleat requires pyjnius '
                        'on Android.'
                    ),
                )
            )
        except Exception as e:
            self._scan_queue.put(
                ('error', fleatError(f'BLE scan thread error: {e}'))
            )

    async def _process_scan_results(self):
        """Receive and handle events from the queue."""
        while self._scanning:
            try:
                item = self._scan_queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.05)
                continue

            if item is None:
                break

            event_type = item[0]
            if event_type == 'device':
                _, address, name, rssi, native_device = item
                device = BLEDevice(
                    address=address,
                    name=name,
                    details=native_device,
                    rssi=rssi,
                )
                self._found_devices[address] = device
                if self._detection_callback:
                    try:
                        result = self._detection_callback(device, None)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass
            elif event_type == 'error':
                raise item[1]

    # --- Class methods (mirrors BleakScanner static interface) ---

    @classmethod
    async def discover(
        cls,
        timeout=5.0,
        *,
        detection_callback=None,
    ):
        """Perform a BLE scan and return all discovered devices.

        Compatible with BleakScanner.discover().

        Args:
            timeout: Duration in seconds to scan. Default is 5.0.
            detection_callback: Optional callback called for each device found.

        Returns:
            A list of BLEDevice objects for all discovered devices.
        """
        scanner = cls(detection_callback=detection_callback)
        async with scanner:
            await asyncio.sleep(timeout)
        return scanner.discovered_devices

    @classmethod
    async def _find_device(
        cls, name=None, address=None, timeout=10.0, **kwargs
    ):
        """Scan for a BLE device with the given name or address."""
        found_event = asyncio.Event()
        found_device = [None]

        def callback(device, _adv_data):
            if (name and device.name == name) or (
                address and device.address.lower() == address.lower()
            ):
                found_device[0] = device
                found_event.set()

        scanner = cls(detection_callback=callback)
        await scanner.start()
        try:
            await asyncio.wait_for(found_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            await scanner.stop()

        return found_device[0]

    @classmethod
    async def find_device_by_name(cls, name, timeout=10.0, **kwargs):
        """Scan for a BLE device with the given name.

        Compatible with BleakScanner.find_device_by_name().

        Args:
            name: The exact device name to search for.
            timeout: Maximum scan duration in seconds. Default is 10.0.

        Returns:
            A BLEDevice if the device was found, or None if the scan timed out.
        """
        return await cls._find_device(name, None, timeout, **kwargs)

    @classmethod
    async def find_device_by_address(cls, address, timeout=10.0, **kwargs):
        """Scan for a BLE device with the given MAC address.

        Compatible with BleakScanner.find_device_by_address().

        Args:
            address: The MAC address string (e.g. 'AA:BB:CC:DD:EE:FF').
            timeout: Maximum scan duration in seconds. Default is 10.0.

        Returns:
            A BLEDevice if the device was found, or None if the scan timed out.
        """
        return await cls._find_device(None, address, timeout, **kwargs)
