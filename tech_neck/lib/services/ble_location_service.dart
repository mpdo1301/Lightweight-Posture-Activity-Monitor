import 'dart:async';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:latlong2/latlong.dart';

class PiPayload {
  final double? lat;
  final double? lng;

  PiPayload({this.lat, this.lng});

  bool get hasGps => lat != null && lng != null;

  factory PiPayload.fromString(String raw) {
    final parts = raw.trim().split(',');
    if (parts.length != 2) return PiPayload();
    final lat = double.tryParse(parts[0]);
    final lng = double.tryParse(parts[1]);
    return PiPayload(lat: lat, lng: lng);
  }
}

class BleLocationService {
  static const String _gpsServiceUuid = "12345678-1234-1234-1234-123456789abc";
  static const String _gpsCharUuid    = "12345678-1234-1234-1234-123456789def";

  static final _gpsController     = StreamController<LatLng>.broadcast();
  static final _payloadController = StreamController<PiPayload>.broadcast();

  static Stream<LatLng>     get gpsStream     => _gpsController.stream;
  static Stream<PiPayload>  get payloadStream => _payloadController.stream;

  static StreamSubscription? _scanSub;
  static StreamSubscription? _notifySub;
  static BluetoothDevice?    _device;

  static Future<void> start() async {
    await FlutterBluePlus.startScan(
      withServices: [Guid(_gpsServiceUuid)],
      timeout: const Duration(seconds: 30),
    );

    _scanSub = FlutterBluePlus.onScanResults.listen((results) async {
      if (results.isEmpty) return;
      await FlutterBluePlus.stopScan();
      await _connect(results.last.device);
    });
  }

  static Future<void> _connect(BluetoothDevice device) async {
    _device = device;
    await device.connect(license: License.free);

    final services = await device.discoverServices();
    for (final service in services) {
      if (service.serviceUuid == Guid(_gpsServiceUuid)) {
        for (final char in service.characteristics) {
          if (char.characteristicUuid == Guid(_gpsCharUuid)) {
            await char.setNotifyValue(true);
            _notifySub = char.lastValueStream.listen((bytes) {
              final payload = PiPayload.fromString(String.fromCharCodes(bytes));
              _payloadController.add(payload);
              if (payload.hasGps) {
                _gpsController.add(LatLng(payload.lat!, payload.lng!));
              }
            });
          }
        }
      }
    }
  }

  static void stop() {
    _scanSub?.cancel();
    _notifySub?.cancel();
    _device?.disconnect();
  }
}