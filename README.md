# fleat
A _very_ limited Bleak complement for accessing Bluetooth LE on Android in Python apps made with Fleat.

## Introduction
**fleat** (a  portmanteau of "Bleak" and "Flet") is a limited complement for [Bleak](https://github.com/hbldh/bleak) to access Bluetooth LE on Android devices from Python apps made with [BeeWare](https://beeware.org/).

Bleak, the 'Bluetooth Low Energy platform Agnostic Klient', allows using Python to access Bluetooth LE cross-platform, but it's existing platform backend for Android requires [python-for-android (P4A)](https://python-for-android.readthedocs.io/en/latest/index.html), which is not compatible with the use of Flet.

fleat is 'usage compatible' to Bleak, meaning that it's methods have the same names and return (mostly) the same data as Bleak. Thus, using platform-dependent import switches, the same code can run on Linux, Mac and Windows using Bleak or on Android using fleat. However, fleat is _not_ dependent on Bleak; if your Python app should only run on Android you don't need to install or import Bleak in addition to fleat.

## Limitations
fleat is a _very limited_ complement for Bleak. It only supports the following methods:
1. With FleatScanner you can scan for available BLE devices (`discover()`) or find a certain device either by its name or address (`find_device_by_name()`, `find_device_by_address()`. The result of these operations is either a list of `BLEDevice` objects or a single `BLEDevice` object.
2. A `BLEDevice` object has a `name`, `address`, `details` (which is the native BLE object) and a `rssi` value (received signal strength indicator).
3. With FleatClient you can connect to and disconnet from a BLE device (`connect()`, `disconnect()`), read from or write to characteristics (`read_gatt_char()`, `write_gatt_char()`), subscribe to and stop notifications (`start_notify()`, `stop_notify()`), and get a list of available services (`get_services()`)
4. fleat is made for Android apps made with Flet and requires [Pyjnius](https://github.com/kivy/pyjnius) to access the Android API
5. fleat requires UUID _strings_ to address services and characteristics


## How to use it
The current set-up procedure requires some manual intervention:

1. Set up a virtual environment to start a new Flet project as described in the [Flet tutorial](https://flet.dev/docs/getting-started/create-flet-app)
2. Install fleat from GitHub via pip: `python -m pip install git+https://github.com/MarkusPiotrowski/fleat`
3. Write and test some code for a desktop computer (Linux, Mac or Window) using **Bleak** to access Bluetooth LE
4. If your code runs fine on your desktop computer, set up an Android build with `flet build apk`

> NOTE: If you do this for the first time, the build can take a _very long_ time, because a Java SDK and the Android SDK will be downloaded and installed on your computer.

> After this first build process, **DO NOT** download the build APK to your phone. This run was for setting up the build directories by Flet.

WORK IN PRGORESS, README.md is rewritten from bleekWare's README.md

~~5. Now, add the following lines to the `pyproject.toml`file of your project: 

4. Before setting up an Android project, copy the following lines into the `tool.briefcase.app.YOURPROJECT.android` section of your `pyproject.toml` file, e.g. below the
`build_gradle_dependencies`:

   ```
   build_gradle_extra_content = "android.defaultConfig.python.staticProxy('bleekWare.Scanner', 'bleekWare.Client')"
   android_manifest_extra_content = """
   <uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
   <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30" />
   <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" android:maxSdkVersion="30" />
   <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" android:maxSdkVersion="30" />
   <uses-permission android:name="android.permission.BLUETOOTH_SCAN" android:usesPermissionFlags="neverForLocation" />
   <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
   """
   ```
      
5. Also add fleat as an installation requirement for Android in the `pyproject.toml` file:

   ```
   [tool.briefcase.app.YOURPROJECT.android]
   requires = [
       "toga-android......",
	   "git+https://github.com/MarkusPiotrowski/bleekWare",
	]
	```
	
6. If your code runs fine on your desktop platform, set up an Android project as described in the [BeeWare tutorial](https://tutorial.beeware.org/tutorial/tutorial-5/)
7. If your application should run cross-platform and you require both Bleak and bleekWare, you may want to use conditional imports like this:
   ```python
   import toga

   if toga.platform.current_platform == 'android':
      from bleekWare import bleekWareError as BLEError
      from bleekWare.Client import Client as Client
      from bleekWare.Scanner import Scanner as Scanner  
   else:
      from bleak import BleakError as BLEError
      from bleak import BleakClient as Client
      from bleak import BleakScanner as Scanner
        
   ...
   ```

## Example code
### Scanner class
See [`android_ble_scanner.py`](Example/android_ble_scanner.py) in the Example folder for different BLE scanning examples. The code is tested to run on Windows (using Bleak) and Android devices (using bleekWare). It should be running on Mac and Linux as well (again using Bleak), but this hasn't been tested.

### Client class
Connecting to a BLE device and reading from or writing to it's characteristics is dependent on the device's capabilities; thus providing a general working example app isn't possible. But here is an outline for connecting to a BLE device and reading from a notifying service:

```python
"""
Connect to and read notifications from a BLE device
"""

import asyncio

import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from toga import Button, MultilineTextInput

if toga.platform.current_platform == 'android':
    from bleekWare import bleekWareError as BLEError
    from bleekWare.Client import Client as Client
    from bleekWare.Scanner import Scanner as Scanner
else:
    from bleak import BleakError as BLEError
    from bleak import BleakScanner as Scanner
    from bleak import BleakClient as Client


# Put here a notifying characteristic of your device:
NOTIFY_UUID = '0000fff1-0000-1000-8000-00805f9b34fb'

# Possibly not available or different UUID:
BATTERY_UUID = '00002a19-0000-1000-8000-00805f9b34fb'  

class bleekWareExample(toga.App):

    def startup(self):
        """Build a little GUI."""
        self.scan_button = Button(
            'Scan for BLE devices', on_press=self.search_device
        )
        self.message_box = MultilineTextInput(
            readonly=True,
            style=Pack(padding=(10, 5), height=200),
        )
        self.data_box = MultilineTextInput(
            readonly=True,
            style=Pack(padding=(10, 5), height=200),
        )
        box = toga.Box(
            children=[
                self.scan_button,
                self.message_box,
                self.data_box
            ],
            style=Pack(direction=COLUMN)
        )        
        self.main_window = toga.MainWindow(title='bleekWare Example')
        self.main_window.content = box
        self.main_window.show()

    async def search_device(self, widget):
        """Search for BLE device by name."""
        device = None
        self.message_box.value = 'Start BLE scan...\n'
        try:
            # Replace the name of your device here:
            device = await Scanner.find_device_by_name('your_device_by_name')

            # Alternatively, you may want to find your device by it's
            # MAC address or UUID (on Mac):
            # device = await Scanner.find_device_by_address('AA:BB:CC:DD:EE:FF'): 

        except (OSError, BLEError) as e:
            self.message_box.value += (
                f'Bluetooth not available. Error: {str(e)}\n'
            )

        if device:
            self.message_box.value += 'Found it!\n'
            await self.connect_to_device(device)
        else:
            self.message_box.value += "Sorry, couldn't find it...\n"

    async def connect_to_device(self, device):
        """Connect to BLE device."""
        self.message_box.value += 'Connecting to device...\n'
        async with Client(device, self.disconnect_callback) as client:
            self.message_box.value += (
                f'Client is connected: {client.is_connected}\n'
            )
            
            # You device probably hasn't a battery level characteristic 
            battery_level = await client.read_gatt_char(BATTERY_UUID)  # if available
            self.message_box.value += (
                'Battery level: '
                f'{int.from_bytes(battery_level, "big")}%\n'
            )
            await client.start_notify(
                NOTIFY_UUID, self.show_data
            )
            await asyncio.Future()

    def disconnect_callback(self, client):
        """Handle disconnection."""
        self.message_box.value += f'DEVICE WAS DISCONNECTED from {client}\n'

    def show_data(self, char, data):
        """Show notifications."""
        self.data_box.value += str(data.hex()) + '\n'


def main():
    return bleekWareExample()

```~~