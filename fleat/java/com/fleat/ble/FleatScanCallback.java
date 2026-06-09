package com.fleat.ble;

import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;

import java.util.List;

/**
 * FleatScanCallback bridges Android's abstract ScanCallback to Python.
 *
 * Same pattern as FleatGattCallback: extends the abstract class in Java,
 * exposes an Interface that Python implements via PythonJavaClass.
 *
 * Usage in Python (Scanner.py):
 *
 *   FleatScanCallback = autoclass('com.fleat.ble.FleatScanCallback')
 *
 *   class PyScanCallback(PythonJavaClass):
 *       __javainterfaces__ = ['com/fleat/ble/FleatScanCallback$Interface']
 *       __javacontext__ = 'app'
 *
 *       @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
 *       def onScanResult(self, callbackType, result): ...
 *
 *       @java_method('(I)V')
 *       def onScanFailed(self, errorCode): ...
 *
 *   callback = PyScanCallback()
 *   bridge = FleatScanCallback(callback)
 *   bluetoothLeScanner.startScan(None, settings, bridge)
 */
public class FleatScanCallback extends ScanCallback {

	public interface Interface {
        void onScanResult(int callbackType, ScanResult result);
        void onBatchScanResults(List<ScanResult> results);
        void onScanFailed(int errorCode);
    }

    private final Interface listener;

    public FleatScanCallback(Interface listener) {
        this.listener = listener;
    }

    @Override
    public void onScanResult(int callbackType, ScanResult result) {
        listener.onScanResult(callbackType, result);
    }

    @Override
    public void onBatchScanResults(List<ScanResult> results) {
        listener.onBatchScanResults(results);
    }

    @Override
    public void onScanFailed(int errorCode) {
        listener.onScanFailed(errorCode);
    }
}
