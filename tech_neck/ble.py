"""
Run with: python ble.py
"""

import time
import threading
import logging
import uvicorn
from bluezero import peripheral, adapter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

GPS_SERVICE_UUID   = "12345678-1234-1234-1234-123456789abc"
GPS_CHAR_UUID      = "12345678-1234-1234-1234-123456789def"
ACTIVITY_CHAR_UUID = "12345678-1234-1234-1234-123456789111"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

lock = threading.Lock()

steps                  = 8432
standing_minutes       = 214
posture_goal_percentage = 68.5
current_activity       = "walking"
idle_streak            = 0

# ---------------------------------------------------------------------------
# GPS
# ---------------------------------------------------------------------------

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

gps = GpsReader()

# ---------------------------------------------------------------------------
# BLE helpers
# ---------------------------------------------------------------------------

def encode(value: str) -> list:
    return list(value.encode('utf-8'))

def activity_string() -> str:
    with lock:
        return f"{steps},{standing_minutes},{posture_goal_percentage}"

# ---------------------------------------------------------------------------
# BLE peripheral thread
# ---------------------------------------------------------------------------

def run_ble():
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
        value=encode(activity_string()), notifying=False,
        flags=['read', 'notify'],
        read_callback=lambda: encode(activity_string()),
        write_callback=None, notify_callback=None,
    )

    pi_peripheral.publish()
    logger.info("BLE peripheral running...")

    while True:
        try:
            pi_peripheral.update_characteristic(1, 1, encode(gps.position_string))
        except Exception:
            pass

        if int(time.time()) % 5 == 0:
            try:
                pi_peripheral.update_characteristic(1, 2, encode(activity_string()))
            except Exception:
                pass

        time.sleep(1)

# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ActivitySummary(BaseModel):
    steps: int
    active_minutes: int
    posture_goal_percentage: float
    current_activity: str
    idle_streak_minutes: int

class GpsPoint(BaseModel):
    lat: float
    lng: float

@app.get("/activity/summary", response_model=ActivitySummary)
def get_activity_summary():
    with lock:
        return ActivitySummary(
            steps=steps,
            active_minutes=standing_minutes,
            posture_goal_percentage=posture_goal_percentage,
            current_activity=current_activity,
            idle_streak_minutes=idle_streak,
        )

@app.get("/gps/route", response_model=List[GpsPoint])
def get_gps_route():
    return [
        GpsPoint(lat=46.8698, lng=-122.2609),
        GpsPoint(lat=46.8712, lng=-122.2615),
        GpsPoint(lat=46.8725, lng=-122.2601),
        GpsPoint(lat=46.8731, lng=-122.2588),
        GpsPoint(lat=46.8740, lng=-122.2572),
        GpsPoint(lat=46.8748, lng=-122.2560),
        GpsPoint(lat=46.8741, lng=-122.2545),
        GpsPoint(lat=46.8730, lng=-122.2538),
        GpsPoint(lat=46.8718, lng=-122.2542),
        GpsPoint(lat=46.8705, lng=-122.2551),
        GpsPoint(lat=46.8698, lng=-122.2565),
        GpsPoint(lat=46.8694, lng=-122.2580),
        GpsPoint(lat=46.8698, lng=-122.2609),
    ]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    gps.start()
    threading.Thread(target=run_ble, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)