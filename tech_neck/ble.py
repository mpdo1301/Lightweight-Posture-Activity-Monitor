import time
import threading
import logging
from bluezero import peripheral, adapter

GPS_SERVICE_UUID   = "12345678-1234-1234-1234-123456789abc"
GPS_CHAR_UUID      = "12345678-1234-1234-1234-123456789def"
ACTIVITY_CHAR_UUID = "12345678-1234-1234-1234-123456789111"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GpsReader:
    def __init__(self):
        self._lat = None
        self._lng = None
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _read_loop(self):
        try:
            import gps as gpslib
            session = gpslib.gps(mode=gpslib.WATCH_ENABLE | gpslib.WATCH_NEWSTYLE)
            while self._running:
                try:
                    report = session.next()
                    if report['class'] == 'TPV':
                        lat = getattr(report, 'lat', None)
                        lng = getattr(report, 'lon', None)
                        self._lat = round(lat, 6) if lat else None
                        self._lng = round(lng, 6) if lng else None
                except StopIteration:
                    break
        except Exception as e:
            logger.warning(f"GPS unavailable: {e}")

    @property
    def position_string(self):
        if self._lat is not None and self._lng is not None:
            return f"{self._lat},{self._lng}"
        return "null,null"


class ActivityData:
    steps = 8432
    standing_minutes = 214
    posture_goal_percentage = 68.5

    @classmethod
    def as_string(cls):
        return f"{cls.steps},{cls.standing_minutes},{cls.posture_goal_percentage}"


def encode(value: str) -> list:
    return list(value.encode('utf-8'))


def main():
    gps = GpsReader()
    gps.start()

    ble = adapter.Adapter()
    ble.powered = True

    pi_peripheral = peripheral.Peripheral(
        ble.address,
        local_name='TechNeckPi',
        appearance=0x0000,
    )

    pi_peripheral.add_service(srv_id=1, uuid=GPS_SERVICE_UUID, primary=True)

    pi_peripheral.add_characteristic(
        srv_id=1, chr_id=1, uuid=GPS_CHAR_UUID,
        value=encode("null,null"), notifying=False,
        flags=['read', 'notify'],
        read_callback=lambda: encode(gps.position_string),
        write_callback=None, notify_callback=None,
    )

    pi_peripheral.add_characteristic(
        srv_id=1, chr_id=2, uuid=ACTIVITY_CHAR_UUID,
        value=encode(ActivityData.as_string()), notifying=False,
        flags=['read', 'notify'],
        read_callback=lambda: encode(ActivityData.as_string()),
        write_callback=None, notify_callback=None,
    )

    pi_peripheral.publish()
    logger.info("PiTracker BLE peripheral running...")

    try:
        while True:
            try:
                pi_peripheral.update_characteristic(1, 1, encode(gps.position_string))
            except Exception:
                pass

            if int(time.time()) % 5 == 0:
                try:
                    pi_peripheral.update_characteristic(1, 2, encode(ActivityData.as_string()))
                except Exception:
                    pass

            time.sleep(1)

    except KeyboardInterrupt:
        gps.stop()
        pi_peripheral.quit()


if __name__ == "__main__":
    main()