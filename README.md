# fleat
A _very_ limited Bleak complement for accessing Bluetooth LE on Android in Python apps made with Flet.

## Introduction
**fleat** (a  portmanteau of "Bleak" and "Flet") is a limited complement for [Bleak](https://github.com/hbldh/bleak) to access Bluetooth LE on Android devices from Python apps made with [Flet](https://https://flet.dev/).

>If you need Bluetooth LE access for [BeeWare](https://beeware.org/), look into my other repo, [bleekWare](https://github.com/MarkusPiotrowski/bleekWare).

**Bleak**, the 'Bluetooth Low Energy platform Agnostic Klient', allows using Python to access Bluetooth LE cross-platform, but it's existing platform backend for Android requires [python-for-android (P4A)](https://python-for-android.readthedocs.io/en/latest/index.html), which is not compatible with the use of Flet.

**fleat** is 'usage compatible' to **Bleak**, meaning that it's methods have the same names and return (mostly) the same data as **Bleak**. Thus, using platform-dependent import switches, the same code can run on Linux, Mac and Windows using **Bleak** or on Android using **fleat**. However, **fleat** is _not_ dependent on **Bleak**; if your Python app should only run on Android you don't need to install or import **Bleak** in addition to **fleat**.

## Limitations
**fleat** is a _very limited_ complement for Bleak. It only supports the following methods:
1. With `FleatScanner` you can scan for available BLE devices (`discover()`) or find a certain device either by its name or address (`find_device_by_name()`, `find_device_by_address()`. The result of these operations is either a list of `BLEDevice` objects or a single `BLEDevice` object.
2. A `BLEDevice` object has a `name`, `address`, `details` (which is the native BLE object) and a `rssi` value (received signal strength indicator).
3. With `FleatClient` you can connect to and disconnet from a BLE device (`connect()`, `disconnect()`), read from or write to characteristics (`read_gatt_char()`, `write_gatt_char()`), subscribe to and stop notifications (`start_notify()`, `stop_notify()`), and get a list of available services (`get_services()`)
4. **fleat** is made for Android apps made with Flet and requires [Pyjnius](https://github.com/kivy/pyjnius) to access the Android API
5. **fleat** requires UUID _strings_ to address services and characteristics


## Installation/Setup
The current set-up procedure for **fleat** requires some manual intervention to add entries to the `pyproject.toml` file and to copy some Java files to their proper destination. But before starting to work on Android, it is recommended that you first write some test code to become familiar with Bluetooth LE access.

### Test Bluetooth LE access on a desktop computer with Bleak
It is recommended that you first test your code for accessing Bluetooth LE on a desktop computer with the established **Bleak** library. This ensures that your code is working as you expects it.
1. Set up a virtual environment to start a new Flet project as described in the [Flet tutorial](https://flet.dev/docs/getting-started/create-flet-app)
2. Install **Bleak** with `python -m pip install bleak`
3. Write and test some code to scan for, connect to and read from a Bluetooth LE device.

### Set up the Android project
4. If you have skipped the steps above, first set up a virtual environment to start a new Flet project as described in the [Flet tutorial](https://flet.dev/docs/getting-started/create-flet-app)
5. Install **fleat** from GitHub via pip: `python -m pip install git+https://github.com/MarkusPiotrowski/fleat`
6. **In your project folder** run `python -m fleat setup-android`.
This will set up a directory structure in `YOUR_PROJECT/build` and adds some required `.java` classes to your project. The final structure will look like this:
    ```
    YOUR_PROJECT
     ├─build
	 │  └─flutter
	 │	    └─android
     │	       └─app
	 │           └─src
	 │              └─main
     │                 └─java
	 │                    ├─com
	 │                    │  └─fleat
	 │                    │     └─ble
	 │                    │        ├─FleatGattCallback.java 
	 │                    │        └─FleatScanCallback.java
	 │                    ├─io
	 │                    └─org
     │                       └─jnius
     │                          └─NativeInvocationHandler.java
     └─src                      	 
	```
	
	> NOTE: Each time you delete the `build` folder or use `flet build --clear-cache` you need to re-build this structure with `python -m fleat setup-android` from within your `YOUR_PROJECT` folder!

7. Next, you need to extend the `pyproject.toml` file of your project. Add the following lines to it (or extend the existing entries accordingly):

    a. Your project requires `pyjnius` and (of course) `fleat` (**fleat** is not available from PyPi, so it's downloaded from this Github repository):
    ```
    [tool.flet.android]
    dependencies = [
        "pyjnius",
        "git+https://github.com/MarkusPiotrowski/fleat"
    ]
    ```

     b. Hardware access on Android devices requires permissions (these entries are added to the `AndroidManifest.xml` during building):
	```
	[tool.flet.android.permission]
	"android.permission.BLUETOOTH" = true
	"android.permission.BLUETOOTH_ADMIN" = true
	"android.permission.ACCESS_COARSE_LOCATION" = true
	"android.permission.ACCESS_FINE_LOCATION" = true
	"android.permission.BLUETOOTH_SCAN" = true
	"android.permission.BLUETOOTH_CONNECT" = true

	[tool.flet.android.feature]
	"android.hardware.bluetooth_le" = true
	```
8. If your application should run cross-platform and you require both **Bleak** and **fleat**, you can use conditional imports like this:
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

9. Now you are ready to build an APK or run the app in debug mode on your phone. Follow the instructions from the Flet documentation [here (building an APK)](https://flet.dev/docs/publish/android) or [here (run the app in debug mode on your phone)](https://flet.dev/blog/flet-debug-the-new-cli-for-testing-flet-apps-on-mobile-devices).

	> NOTE: If you do this for the first time, the build can take a _very long_ time, because a Java JDK and the Android SDK will be downloaded and installed on your computer.


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
        if connected:
            search_tile.title = f'Already connected to {device.name}'
            page.update()
            return
        search_tile.title = 'Searching for device...'
        page.update()
        try:
            device = await Scanner.find_device_by_name('THE_NAME_OF_YOUR_DEVICE')
            # Alternatively, you may want to find your device by it's
            # MAC address or UUID (on Mac):
            # = await Scanner.find_device_by_address('AA:BB:CC:DD:EE:FF')
        except (OSError, BluetoothError) as e:
            search_tile.title = f'Bluetooth Error: {e}'

        if device:
            search_tile.title = f'Found device {device.name}!'
        else:
            search_tile.title = "Sorry, couldn't find it"
        page.update()

    async def _connect_and_read_from_device(e):
        """Connect to found BLE device and receive notifications."""
        nonlocal connected
        if not device:
            search_tile.title = 'Not connected'
            return
        async with Client(device, disconnect_callback) as client:
            search_tile.title = f'Connected to {device.name}'
            connected = True

            # Read a simple characteristic:
            try:
                # You device probably hasn't a battery level characteristic
                battery_level = await client.read_gatt_char(BATTERY_UUID)
                battery_tile.title = f'{int.from_bytes(battery_level, "big")}%'
            except BluetoothError:
                battery_tile.title = 'Not available'

            # Subscribe to a notifying characteristic
            await client.start_notify(NOTIFY_UUID, show_notifications)

            page.update()
            await asyncio.Future()

    def disconnect_callback(client):
        """Handle disconnection."""
        nonlocal connected
        search_tile.title = 'Disconnected...'
        connected = False
        page.update()

    def show_notifications(char, data):
        """Display the notifications."""
        notification_tile.title = f'{data.hex()}'
        page.update()

    # Text fields:
    search_tile = ft.ListTile(
        leading=ft.Icon(ft.Icons.BLUETOOTH),
        title='',
        subtitle='Status',
        margin=20,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    battery_tile = ft.ListTile(
        leading=ft.Icon(ft.Icons.BATTERY_4_BAR),
        title='',
        subtitle='Battery Level',
        margin=20,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    notification_tile = ft.ListTile(
        leading=ft.Icon(ft.Icons.MESSAGE),
        title='',
        subtitle='Notifications',
        margin=20,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )

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
    button_row = ft.ResponsiveRow(
        columns=2,
        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        margin=20,
        controls=[
            ft.Container(
                col={
                    ft.ResponsiveRowBreakpoint.XS: 2,
                    ft.ResponsiveRowBreakpoint.MD: 1,
                },
                content=search_button,
            ),
            ft.Container(
                col={
                    ft.ResponsiveRowBreakpoint.XS: 2,
                    ft.ResponsiveRowBreakpoint.MD: 1,
                },
                content=connect_button,
            ),
        ],
    )

    # Page:
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    search_tile,
                    battery_tile,
                    notification_tile,
                    button_row,
                ],
            ),
        )
    )


ft.run(main)
```
