"""Realistic Marstek Venus E telemetry simulator for demo / UI development."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field


@dataclass
class SimulatorState:
    soc_pct: float = 87.0
    home_load_w: float = 610.0
    grid_input_w: float = 0.0
    solar_power_w: float = 0.0
    battery_power_w: float = -610.0  # net into battery (+ charge / - discharge)
    station_self_w: float = 10.0
    temp_c: float = 28.5
    voltage_v: float = 51.2
    mode: str = "Auto"
    power_limit_w: int = 1500
    daily_charged_kwh: float = 4.2
    daily_discharged_kwh: float = 3.1
    _t0: float = field(default_factory=time.time)
    _manual: bool = False
    _chart: list[dict] = field(default_factory=list)

    def apply_override(
        self,
        *,
        home_load_w: float | None = None,
        grid_input_w: float | None = None,
        soc_pct: float | None = None,
        battery_power_w: float | None = None,
        temp_c: float | None = None,
    ) -> None:
        self._manual = True
        if home_load_w is not None:
            self.home_load_w = home_load_w
        if grid_input_w is not None:
            self.grid_input_w = grid_input_w
        if soc_pct is not None:
            self.soc_pct = max(0.0, min(100.0, soc_pct))
        if battery_power_w is not None:
            self.battery_power_w = battery_power_w
        if temp_c is not None:
            self.temp_c = temp_c
        self._rebalance()

    def _rebalance(self) -> None:
        # Approximate energy balance: grid + solar + (-battery_discharge) ≈ home
        # battery_power_w: + = charging from surplus, - = discharging to load
        if self._manual and abs(self.battery_power_w) > 1:
            return
        self.solar_power_w = 0.0
        surplus = self.grid_input_w - self.home_load_w
        # Clamp to power limit
        limit = float(self.power_limit_w)
        self.battery_power_w = max(-limit, min(limit, surplus))

    def tick(self, dt: float = 2.0) -> None:
        now = time.time()
        elapsed = now - self._t0

        self.solar_power_w = 0.0
        if not self._manual:
            wave = 55 * math.sin(elapsed / 17.0) + 28 * math.sin(elapsed / 6.4)
            bump = 45.0 if int(elapsed / 3) % 11 in (0, 1) else 0.0
            self.home_load_w = min(700.0, max(500.0, 590 + wave + bump + random.uniform(-18, 18)))
            # The house is on the grid meter. The station's own idle draw is separate.
            self.grid_input_w = self.home_load_w
            self.station_self_w = min(12.0, max(8.0, 10.0 + random.uniform(-1.4, 1.4)))
            limit = float(self.power_limit_w)
            self.battery_power_w = max(-limit, -self.home_load_w)

        # Integrate SOC
        # battery_power_w positive => charging
        delta_wh = self.battery_power_w * (dt / 3600.0)
        capacity = 5120.0
        self.soc_pct = max(0.0, min(100.0, self.soc_pct + (delta_wh / capacity) * 100.0))

        # Daily counters
        if self.battery_power_w > 0:
            self.daily_charged_kwh += (self.battery_power_w * dt) / 3_600_000.0
        elif self.battery_power_w < 0:
            self.daily_discharged_kwh += (abs(self.battery_power_w) * dt) / 3_600_000.0

        # Thermal / voltage
        self.temp_c = 26.0 + abs(self.battery_power_w) / 800.0 + random.uniform(-0.2, 0.2)
        self.voltage_v = 48.0 + (self.soc_pct / 100.0) * 6.4 + random.uniform(-0.05, 0.05)

    def snapshot(self) -> dict:
        return {
            "soc_pct": round(self.soc_pct, 2),
            "home_load_w": round(self.home_load_w, 1),
            "grid_input_w": round(self.grid_input_w, 1),
            "solar_power_w": round(self.solar_power_w, 1),
            "battery_power_w": round(self.battery_power_w, 1),
            "station_self_w": round(self.station_self_w, 1),
            "temp_c": round(self.temp_c, 1),
            "voltage_v": round(self.voltage_v, 2),
            "mode": self.mode,
            "power_limit_w": self.power_limit_w,
            "daily_charged_kwh": round(self.daily_charged_kwh, 2),
            "daily_discharged_kwh": round(self.daily_discharged_kwh, 2),
            "latency_ms": random.randint(8, 22),
            "device_model": "VenusE",
            "firmware": 153,
            "wifi_ssid": "Home",
            "wifi_rssi": -58,
            "ble_state": "connect",
            "charge_allowed": True,
            "discharge_allowed": True,
            "rated_capacity_wh": 5120,
            "total_grid_import_kwh": 186.4,
            "total_grid_export_kwh": 22.8,
            "total_load_kwh": 9.4,
            "total_pv_kwh": 0.0,
            "ct_connected": True,
            "ct_power_w": round(self.grid_input_w, 1),
            "ct_a_w": round(self.grid_input_w, 1),
            "ct_b_w": 0.0,
            "ct_c_w": 0.0,
            "history": self._chart_points(),
        }

    def _chart_points(self) -> list[dict]:
        """Rolling day of battery power. Positive = charge, negative = discharge."""
        now = time.time()
        if not self._chart:
            self._chart = self._seed_day(now)
        step = 10 * 60
        if now - float(self._chart[-1]["ts"]) >= step:
            self._chart.append(self._point(now, self.battery_power_w))
            cutoff = now - 24 * 3600
            self._chart = [point for point in self._chart if float(point["ts"]) >= cutoff]
        else:
            self._chart[-1] = self._point(now, self.battery_power_w)
        return list(self._chart)

    def _point(self, ts: float, power: float) -> dict:
        return {
            "ts": ts,
            "soc_pct": round(self.soc_pct, 2),
            "power_w": round(power, 1),
        }

    def _seed_day(self, now: float) -> list[dict]:
        step = 10 * 60
        start = now - 24 * 3600
        points: list[dict] = []
        cursor = start
        while cursor < now - 15:
            points.append(self._point(cursor, self._day_power(cursor)))
            cursor += step
        points.append(self._point(now, self.battery_power_w))
        return points

    def _day_power(self, ts: float) -> float:
        """Household-shaped battery power for one 10-minute slice."""
        clock = time.localtime(ts)
        hour = clock.tm_hour + clock.tm_min / 60.0
        rng = random.Random(int(ts // 600))
        # Night window charges from the grid. The rest of the day the house draws the battery.
        if 1.0 <= hour < 5.5:
            power = 480 + 320 * math.sin((hour - 1.0) / 4.5 * math.pi)
        elif 6.5 <= hour < 9.0:
            power = -780 - 420 * math.sin((hour - 6.5) / 2.5 * math.pi)
        elif 17.0 <= hour < 22.0:
            power = -640 - 480 * math.sin((hour - 17.0) / 5.0 * math.pi)
        elif 9.0 <= hour < 17.0:
            power = -460 - 140 * math.sin(hour / 2.4)
        else:
            power = -180 - 70 * math.sin(hour / 3.0)
        if power < 0 and rng.random() < 0.22:
            power -= rng.choice((280, 460, 720, 980))
        elif power > 0 and rng.random() < 0.2:
            power += rng.uniform(-80, 160)
        power += rng.uniform(-35, 35)
        return max(-2200.0, min(1400.0, power))
