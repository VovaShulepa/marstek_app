"""Write-only device settings. The Venus UDP API accepts DOD, LED, schedules
and the power class, but does not return them."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ManualSlot

PREFS_PATH = Path(__file__).resolve().parents[1] / "data" / "device_prefs.json"
POWER_VERSIONS = (800, 1200, 1500, 2200, 2500)


class DevicePrefs:
    def __init__(self, path: Path = PREFS_PATH) -> None:
        self.path = path
        self.dod_pct = 88
        self.led_on: bool | None = None
        self.ble_broadcast: bool | None = None
        self.power_version_w = 2500
        self.passive_countdown_s = 300
        self.passive_direction = "discharge"
        self.schedules: list[ManualSlot] = []
        self.self_draw_w: float | None = None
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        dod = data.get("dod_pct")
        if isinstance(dod, int) and 30 <= dod <= 88:
            self.dod_pct = dod
        if isinstance(data.get("led_on"), bool):
            self.led_on = data["led_on"]
        if isinstance(data.get("ble_broadcast"), bool):
            self.ble_broadcast = data["ble_broadcast"]
        version = data.get("power_version_w")
        if version in POWER_VERSIONS:
            self.power_version_w = int(version)
        countdown = data.get("passive_countdown_s")
        if isinstance(countdown, int) and 0 <= countdown <= 86400:
            self.passive_countdown_s = countdown
        if data.get("passive_direction") in ("charge", "discharge"):
            self.passive_direction = data["passive_direction"]
        measured = data.get("self_draw_w")
        if isinstance(measured, (int, float)) and measured >= 5:
            self.self_draw_w = float(measured)
        slots: list[ManualSlot] = []
        for item in data.get("schedules") or []:
            try:
                slots.append(ManualSlot.model_validate(item))
            except Exception:
                continue
        self.schedules = slots

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dod_pct": self.dod_pct,
            "led_on": self.led_on,
            "ble_broadcast": self.ble_broadcast,
            "power_version_w": self.power_version_w,
            "passive_countdown_s": self.passive_countdown_s,
            "passive_direction": self.passive_direction,
            "self_draw_w": self.self_draw_w,
            "schedules": [slot.model_dump() for slot in self.schedules],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert_slot(self, slot: ManualSlot) -> None:
        self.schedules = [item for item in self.schedules if item.time_num != slot.time_num]
        self.schedules.append(slot)
        self.schedules.sort(key=lambda item: item.time_num)

    def active_slot(self) -> ManualSlot | None:
        for slot in self.schedules:
            if slot.enable:
                return slot
        return self.schedules[0] if self.schedules else None
