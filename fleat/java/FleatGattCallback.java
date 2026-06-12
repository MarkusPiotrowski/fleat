package com.fleat.ble;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;

import android.os.Handler;
import android.os.Looper;

/**
 * FleatGattCallback bridges Android's abstract BluetoothGattCallback to Python.
 *
 * pyjnius's PythonJavaClass can only implement Java *interfaces*, not extend
 * abstract classes. This class extends BluetoothGattCallback in Java and
 * exposes an Interface that Python can implement via PythonJavaClass.
 *
 * Usage in Python (Scanner.py):
 *
 *   from jnius import autoclass, PythonJavaClass, java_method
 *   FleatGattCallback = autoclass('com.fleat.ble.FleatGattCallback')
 *
 *   class PyGattCallback(PythonJavaClass):
 *       __javainterfaces__ = ['com/fleat/ble/FleatGattCallback$Interface']
 *       __javacontext__ = 'app'
 *
 *       @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
 *       def onConnectionStateChange(self, gatt, status, newState): ...
 *       ...
 *
 *   callback = PyGattCallback()
 *   bridge = FleatGattCallback(callback)
 *   device.connectGatt(context, False, bridge)
 *
 * Pattern based on bleak's PythonBluetoothGattCallback:
 *   https://github.com/hbldh/bleak/tree/develop/bleak/backends/p4android/java
 */
public class FleatGattCallback extends BluetoothGattCallback {

    public interface Interface {
        void onConnectionStateChange(int status, int newState);
        void onServicesDiscovered(int status);
        void onCharacteristicRead(String uuid, byte[] value, int status);
        void onCharacteristicWrite(String uuid, int status);
        void onCharacteristicChanged(String uuid, byte[] value);
        void onDescriptorWrite(String uuid, int status);
        void onMtuChanged(int mtu, int status);
    }

    private final Interface listener;
	
	private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public FleatGattCallback(Interface listener) {
        this.listener = listener;
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, final int status, final int newState) {
        mainHandler.post(() -> listener.onConnectionStateChange(status, newState));
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, final int status) {
        mainHandler.post(() -> listener.onServicesDiscovered(status));
    }

    @Override
    public void onCharacteristicRead(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, final int status) {
		final String uuid = characteristic.getUuid().toString();
        final byte[] value = characteristic.getValue();
        mainHandler.post(() -> listener.onCharacteristicRead(uuid, value, status));
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, final int status) {
        final String uuid = characteristic.getUuid().toString();
		mainHandler.post(() -> listener.onCharacteristicWrite(uuid, status));
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
        final String uuid = characteristic.getUuid().toString();
        final byte[] value = characteristic.getValue();
		mainHandler.post(() -> listener.onCharacteristicChanged(uuid, value));
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, final int status) {
        final String uuid = descriptor.getUuid().toString();
		mainHandler.post(() -> listener.onDescriptorWrite(uuid, status));
    }

    @Override
    public void onMtuChanged(BluetoothGatt gatt, final int mtu, final int status) {
        mainHandler.post(() -> listener.onMtuChanged(mtu, status));
    }
}
