import 'dart:async';
import 'package:latlong2/latlong.dart';
import 'ble_location_service.dart' show PiPayload;

class BleLocationService {
  static final _gpsController     = StreamController<LatLng>.broadcast();
  static final _payloadController = StreamController<PiPayload>.broadcast();

  static Stream<LatLng>    get gpsStream     => _gpsController.stream;
  static Stream<PiPayload> get payloadStream => _payloadController.stream;

  static Future<void> start() async {}
  static void stop() {}
}