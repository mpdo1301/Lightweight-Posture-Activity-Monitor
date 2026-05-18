import 'dart:async';
import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:latlong2/latlong.dart';

import 'ble_location_service.dart'
    if (dart.library.html) 'stub_ble_location_service.dart';
import 'phone_location_service.dart'
    if (dart.library.html) 'stub_phone_location_service.dart';

enum GpsSource { bluetooth, phone, http }

class LocationPoint {
  final LatLng position;
  final GpsSource source;
  LocationPoint(this.position, this.source);
}

class LocationService {
  final _controller = StreamController<LocationPoint>.broadcast();
  Stream<LocationPoint> get stream => _controller.stream;

  bool _piHasGpsFix = false;
  bool _bleConnected = false;
  StreamSubscription? _bleGpsSub;
  StreamSubscription? _blePayloadSub;
  StreamSubscription? _phoneSub;
  Timer? _bleConnectionTimer;

  Future<void> start() async {
    if (kIsWeb) return;
    if (!Platform.isAndroid && !Platform.isIOS) return;

    // If no BLE connection within 15s, fall back to phone GPS
    _bleConnectionTimer = Timer(const Duration(seconds: 15), () {
      if (!_bleConnected) _startPhoneGps();
    });

    _blePayloadSub = BleLocationService.payloadStream.listen((payload) {
      _bleConnected = true;
      _bleConnectionTimer?.cancel();

      if (!payload.hasGps && !_piHasGpsFix) {
        _startPhoneGps();
      } else if (payload.hasGps && !_piHasGpsFix) {
        _piHasGpsFix = true;
        _stopPhoneGps();
      }
    });

    _bleGpsSub = BleLocationService.gpsStream.listen((latLng) {
      _piHasGpsFix = true;
      _stopPhoneGps();
      _controller.add(LocationPoint(latLng, GpsSource.bluetooth));
    });

    await BleLocationService.start();
  }

  void _startPhoneGps() {
    if (_phoneSub != null) return;
    _phoneSub = PhoneLocationService.stream.listen((latLng) {
      if (!_piHasGpsFix) {
        _controller.add(LocationPoint(latLng, GpsSource.phone));
      }
    });
    PhoneLocationService.start();
  }

  void _stopPhoneGps() {
    _phoneSub?.cancel();
    _phoneSub = null;
    PhoneLocationService.stop();
  }

  void dispose() {
    _bleConnectionTimer?.cancel();
    _bleGpsSub?.cancel();
    _blePayloadSub?.cancel();
    _stopPhoneGps();
    BleLocationService.stop();
    _controller.close();
  }
}