"""
fleat - A limited replacement for Bleak to use BLE on Android
within the Flet framework.


(c) 2026 by Markus Piotrowski

MIT license
"""

__version__ = "0.1.0"
__author__ = "Markus Piotrowski"


class fleatError(Exception):
    """Base exception class for fleat errors."""

    pass


def _fix_class_loader():
    """Switch the class loader to the app class loader.

    pyjnius uses the system class loader by default, which does not allow
    for loading user-defined Java classes.

    Therefore we set the class-loader context to the current app class loader.
    """
    from jnius import autoclass

    activity = _get_activity()
    class_loader = activity.getClass().getClassLoader()

    Thread = autoclass('java.lang.Thread')
    Thread.currentThread().setContextClassLoader(class_loader)


def _get_activity():
    """Find and return the current Android activity instance.

    According to the Flet docs.
    """
    import os
    from jnius import autoclass

    activity_host_class = os.getenv('MAIN_ACTIVITY_HOST_CLASS_NAME')
    if activity_host_class:
        return autoclass(activity_host_class).mActivity

    # Alternative method:
    activity = autoclass(
        "com.flet.serious_python_android.PythonActivity"
    ).mActivity

    if activity:
        return activity

    raise fleatError('Android activity could not be determined')


def check_for_permissions(activity=None):
    """Check for and request neccessary BLE permissions.

    Since we cannot easily pass BLE permission settings to the
    AndroidManifest.xml with Flet, we do not distinguish if
    ACCESS_FINE_LOCATION is still required, instead we always ask for it.

    May change in future if we are able to pass more specific BLE settings
    from pyproject.toml to AndroidManifest.xml.
    """
    from jnius import autoclass

    if activity is None:
        activity = _get_activity()

    Build = autoclass('android.os.Build$VERSION')
    Manifest = autoclass('android.Manifest$permission')
    PackageManager = autoclass('android.content.pm.PackageManager')

    api_level = Build.SDK_INT

    if api_level > 30:
        # Android 12+: BLUETOOTH_SCAN and BLUETOOTH_CONNECT.
        # ACCESS_FINE_LOCATION would not be requireds if we could
        # set neverForLocation in the manifest.
        permissions = [
            Manifest.BLUETOOTH_SCAN,
            Manifest.BLUETOOTH_CONNECT,
            Manifest.ACCESS_FINE_LOCATION,
        ]
    elif api_level >= 23:
        # Android 6–11: ACCES_FINE_LOCATION is absolutely required
        permissions = [Manifest.ACCESS_FINE_LOCATION]
    else:
        # Android <6: does only require declarations in AndroidManifest.xml
        return

    permissions_granted = all(
        activity.checkSelfPermission(permission)
        == PackageManager.PERMISSION_GRANTED
        for permission in permissions
    )

    if not permissions_granted:
        activity.requestPermissions(permissions, 101)
