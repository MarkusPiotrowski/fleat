"""
BLEDevice - A data class representing a discovered BLE device.
"""


class BLEDevice:
    """Represents a discovered Bluetooth LE device.

    Attributes:
        address (str): The MAC address of the device (e.g.
            'AA:BB:CC:DD:EE:FF').
        name (str | None): The advertised name of the device, or None if not
            available.
        details: The underlying native Android BluetoothDevice Java object.
        rssi (int): The received signal strength indicator (RSSI) at the time
            of discovery.
    """

    def __init__(self, address, name=None, details=None, rssi=0):
        """Initialize a BLEDevice.

        Args:
            address: The MAC address string of the device.
            name: The device name, or None if not available.
            details: The native Android BluetoothDevice Java object (pyjnius).
            rssi: Signal strength in dBm at discovery time.
        """
        self._address = address
        self._name = name
        self._details = details
        self._rssi = rssi

    @property
    def address(self):
        """The MAC address of the BLE device."""
        return self._address

    @property
    def name(self):
        """The advertised name of the BLE device, or None."""
        return self._name

    @property
    def details(self):
        """The native Android BluetoothDevice Java object."""
        return self._details

    @property
    def rssi(self):
        """The RSSI (signal strength) value at the time of discovery."""
        return self._rssi

    def __str__(self):
        return (
            f'BLEDevice(address={self._address}, '
            f'name={self._name}, rssi={self._rssi})'
        )

    def __repr__(self) -> str:
        return self.__str__()
