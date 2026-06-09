# fleat
A _very_ limited Bleak complement for accessing Bluetooth LE on Android in Python apps made with Flet.

## Introduction
**fleat** (a  portmanteau of "Bleak" and "Flet") is a limited complement for [Bleak](https://github.com/hbldh/bleak) to access Bluetooth LE on Android devices from Python apps made with [Flet](https://https://flet.dev/).

Bleak, the 'Bluetooth Low Energy platform Agnostic Klient', allows using Python to access Bluetooth LE cross-platform, but it's existing platform backend for Android requires [python-for-android (P4A)](https://python-for-android.readthedocs.io/en/latest/index.html), which is not compatible with the use of Flet.

fleat is 'usage compatible' to Bleak, meaning that it's methods have the same names and return (mostly) the same data as Bleak. Thus, using platform-dependent import switches, the same code can run on Linux, Mac and Windows using Bleak or on Android using fleat. However, fleat is _not_ dependent on Bleak; if your Python app should only run on Android you don't need to install or import Bleak in addition to fleat.

## Limitations
fleat is a _very limited_ complement for Bleak. It only supports the following methods:
1. With FleatScanner you can scan for available BLE devices (`discover()`) or find a certain device either by its name or address (`find_device_by_name()`, `find_device_by_address()`. The result of these operations is either a list of `BLEDevice` objects or a single `BLEDevice` object.
2. A `BLEDevice` object has a `name`, `address`, `details` (which is the native BLE object) and a `rssi` value (received signal strength indicator).
3. With FleatClient you can connect to and disconnet from a BLE device (`connect()`, `disconnect()`), read from or write to characteristics (`read_gatt_char()`, `write_gatt_char()`), subscribe to and stop notifications (`start_notify()`, `stop_notify()`), and get a list of available services (`get_services()`)
4. fleat is made for Android apps made with Flet and requires [Pyjnius](https://github.com/kivy/pyjnius) to access the Android API
5. fleat requires UUID _strings_ to address services and characteristics


## Installation/Setup
The current set-up procedure requires some manual intervention:

1. Set up a virtual environment to start a new Flet project as described in the [Flet tutorial](https://flet.dev/docs/getting-started/create-flet-app)
2. Install fleat from GitHub via pip: `python -m pip install git+https://github.com/MarkusPiotrowski/fleat`
3. Write and test some code for a desktop computer (Linux, Mac or Window) using **Bleak** to access Bluetooth LE
4. If your code runs fine on your desktop computer, set up an Android build with `flet build apk`

> NOTE: If you do this for the first time, the build can take a _very long_ time, because a Java JDK and the Android SDK will be downloaded and installed on your computer.

> After this first build process, **DO NOT** download the build APK to your phone. This run was for setting up the build directories by Flet.

5. Now, we need to extend the`pyproject.toml` file or your project. Add the following lines to it (or extend the existing entries accordingly).
   a. Your APK requires `pyjnius` and (of course) `fleat` (fleat is not available from PyPi, so it's downloaded from this Github repository):
```
`[tool.flet.android]
dependencies = [
    "pyjnius",
    "git+https://github.com/MarkusPiotrowski/fleat"
]
```
    b. Hardware access on Android devices requires permissions (these entries are added to the `AndroidManifest.xml` during building):
	```
	[tool.flet.android.permission]
	android.permission.BLUETOOTH" = true
	"android.permission.BLUETOOTH_ADMIN"
	"android.permission.ACCESS_COARSE_LOCATION"
	"android.permission.ACCESS_FINE_LOCATION"
	"android.permission.BLUETOOTH_SCAN"
	"android.permission.BLUETOOTH_CONNECT"

	[tool.flet.android.feature]
	"android.hardware.bluetooth_le" = true
	```

6. Finally, we also have to copy two `.java` files into their proper place so that they are included by Gradle, the Android APK packing tool.
Find the folder `YOURPROJECT\build\flutter\android\app\src\main\java` Usually, this folder already includes a folder `io`. Add the following folders and files to get a final structure like this (note: we don't touch the `ìo` folder):
	```
	java
	  ├─com
	  │  └-fleat
	  │     └-ble
	  │        ├─FleatGattCallback.java
	  │        └-FleatScanCallback.java
	  └-io 
	```
	You find the required files in the fleat package's `java` folder. Just copy/paste the `com` folder from there to the build's java folder.

7. Now we are ready to finally build our APK (or run the app in debug mode on your phone) 
8. If your application should run cross-platform and you require both Bleak and fleat, you may want to use conditional imports like this:
   ```python
   import sys
   
   import flet as ft
   
   is_android = sys.platform == 'android' or hasattr(sys, 'getandroidapilevel')

	# import switch for Android
	if is_android:
		from fleat.Scanner import FleatScanner as Scanner
		from fleat.Client import FleatClient as Client
		from fleat import fleatError as BluetoothError
	else:
		from bleak import BleakScanner as Scanner
		from bleak import BleakClient as Client
		from bleak import BleakError as BluetoothError
    
   ...
   ```

## Example code
Connecting to a BLE device and reading from or writing to it's characteristics is dependent on the device's capabilities; thus providing a general working example app isn't possible. But here is an outline for connecting to a BLE device and reading from a notifying service:

```python
"""
Scan for, connect to and read notifications from a BLE device
"""
import asyncio
import sys

import flet as ft

is_android = sys.platform == 'android' or hasattr(sys, 'getandroidapilevel')

# Import switch for Android
if is_android:
    from fleat.Scanner import FleatScanner as Scanner
    from fleat.Client import FleatClient as Client
    from fleat import fleatError as BluetoothError
else:
    from bleak import BleakScanner as Scanner
    from bleak import BleakClient as Client
    from bleak import BleakError as BluetoothError


# Put here a notifying characteristic of your device:
NOTIFY_UUID = '0000fff1-0000-1000-8000-00805f9b34fb'
# Another characteristic to read from, e.g. battery status:
BATTERY_UUID = '00002a19-0000-1000-8000-00805f9b34fb'


def main(page: ft.Page):
    page.title = 'fleat example'

    device = None  # The BLE device to connect to
    connected = False  # If the BLE device is (already) connected

    async def _search_for_device(e):
        """Use Scanner.find_device... to look for a certain device."""
        nonlocal device
        search_text.value = 'Status: Searching for device...'
        page.update()
        try:
            device = await Scanner.find_device_by_name('YOUR_DEVICE')
            # Alternatively, you may want to find your device by it's
            # MAC address or UUID (on Mac):
            # device = await Scanner.find_device_by_address('AA:BB:CC:DD:EE:FF'):
        except (OSError, BluetoothError) as e:
            search_text.value = f'Bluetooth Error: {e}'

        if device:
            search_text.value = f'Status: Found device {device.name}!'
        else:
            search_text.value = "Status: Sorry, couldn't find it"
        page.update()

    async def _connect_and_read_from_device(e):
        """Connect to found BLE device and receive notifications."""
        if not device:
            search_text.value = 'Status: Not connected'
            return
        async with Client(device, disconnect_callback) as client:
            search_text.value = f'Status: Connected to {device.name}'
            connected = True

            # Read a simple characteristic:
            try:
                # You device probably hasn't a battery level characteristic 
                battery_level = await client.read_gatt_char(BATTERY_UUID)
            except BluetoothError:
                batterie_text.value = 'Battery level: Not available'

            # Subscribe to a notifying characteristic
            await client.start_notify(NOTIFY_UUID, show_notifications)

            page.update()
            await asyncio.Future()

    def disconnect_callback(client):
        """Handle disconnection."""
        nonlocal connected
        search_text.value = 'Status: Disconnected...'
        connected = False
        page.update()

    def show_notifications(char, data):
        """Display the notifications."""
        notification_text.value = f'Notification: {data.hex()}'
        page.update()
    

    # Text fields:
    search_text = ft.Text('Status:', size=30)
    batterie_text = ft.Text('Battery level:', size=30)
    notification_text = ft.Text(f'Notification:', size=30)

    # Buttons
    search_button = ft.FloatingActionButton(
        icon=ft.Icons.BLUETOOTH_SEARCHING,
        content='Search for device',
        on_click=_search_for_device,
    )
    connect_button = ft.FloatingActionButton(
        icon=ft.Icons.DOWNLOAD,
        content='Read data from device',
        on_click=_connect_and_read_from_device,
    )
    button_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        controls=[
            search_button,
            connect_button,
        ]
    )

    # Page:
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    search_text,
                    batterie_text,
                    notification_text,
                    button_row,
                ]
            )
        )
    )


ft.run(main)
```