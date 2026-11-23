"""Rolling-average power smoother and time-remaining estimator."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

# With the house idle, the inverter still burns about 10% of the pack in 12 hours.
# Real quiet stretches replace this guess once telemetry has enough SOC drop.
STATION_SELF_SOC_PER_12H = 0.10


def station_self_w(capacity_wh: float, measured_w: float | None = None) -> float:
    if measured_w is not None and measured_w >= 5:
        return float(measured_w)
    if capacity_wh <= 0:
        return 0.0
    return capacity_wh * STATION_SELF_SOC_PER_12H / 12.0


@dataclass
class PowerSample:
    ts: float
    power_w: float


@dataclass
class TimeEstimator:
    """Maintains a rolling window of battery power and estimates time remaining.

    Convention: positive power_w = charging, negative = discharging.
    """

    capacity_wh: float = 5120.0
    min_soc_reserve_pct: float = 12.0
    efficiency: float = 0.95
    window_seconds: int = 12
    self_draw_w: float | None = None
    _samples: deque[PowerSample] = field(default_factory=deque)

    def push(self, power_w: float, ts: float | None = None) -> None:
        now = ts if ts is not None else time.time()
        self._samples.append(PowerSample(ts=now, power_w=power_w))
        self._trim(now)

    def _trim(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._samples and self._samples[0].ts < cutoff:
            self._samples.popleft()

    @property
    def average_power_w(self) -> float:
        """Median of the last few seconds.

        A two-minute mean kept the quiet load and left the clock at 22 hours
        after the house had already stepped up. The short median follows a
        load that holds and skips a one-off spike.
        """
        if not self._samples:
            return 0.0
        now = self._samples[-1].ts
        recent = [sample.power_w for sample in self._samples if now - sample.ts <= 6]
        values = sorted(recent or [sample.power_w for sample in self._samples])
        return values[len(values) // 2]

    def self_draw_watts(self) -> float:
        return station_self_w(self.capacity_wh, self.self_draw_w)

    def available_wh(self, soc_pct: float) -> float:
        """Usable energy above the configured minimum reserve SOC."""
        reserve = self.capacity_wh * (self.min_soc_reserve_pct / 100.0)
        current = self.capacity_wh * (max(0.0, min(100.0, soc_pct)) / 100.0)
        return max(0.0, current - reserve)

    def chargeable_wh(self, soc_pct: float) -> float:
        current = self.capacity_wh * (max(0.0, min(100.0, soc_pct)) / 100.0)
        return max(0.0, self.capacity_wh - current)

    def estimate(
        self, soc_pct: float, instant_power_w: float | None = None
    ) -> tuple[int | None, str, str]:
        """Return (seconds, label HH год MM хв, subtitle)."""
        avg = self.average_power_w
        instant = instant_power_w if instant_power_w is not None else avg

        # Prefer smoothed avg, but if sign just flipped use instant wattage
        if abs(avg) >= 15 and abs(instant) >= 15 and (avg * instant) < 0:
            power = instant
            self._samples.clear()
            self.push(instant)
        elif abs(avg) >= 15:
            power = avg
        else:
            power = instant

        # Idle watts are not a forecast. A guessed self-consumption turned 4 kWh into "98 год".
        if abs(power) < 30:
            return None, "—", "Без навантаження"

        # Discharge: power negative
        if power < 0:
            avail = self.available_wh(soc_pct)
            if avail <= 0:
                return 0, "00 год 00 хв", f"До розряду (до {int(self.min_soc_reserve_pct)}%)"
            # House watts are AC. The inverter also eats DC on its own — measured when quiet, else ~10%/12h.
            effective = abs(power) / max(self.efficiency, 0.01) + self.self_draw_watts()
            seconds = int((avail / effective) * 3600)
            label = format_duration(seconds)
            return seconds, label, f"До розряду (до {int(self.min_soc_reserve_pct)}%)"

        # Charge: power positive
        remaining = self.chargeable_wh(soc_pct)
        if remaining <= 0:
            return 0, "00 год 00 хв", "До 100% заряду"
        effective = power * max(self.efficiency, 0.01)
        seconds = int((remaining / effective) * 3600)
        label = format_duration(seconds)
        return seconds, label, "До 100% заряду"


def format_duration(seconds: int) -> str:
    seconds = max(0, seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 240:
        hours = 240
        minutes = 0
    return f"{hours:02d} год {minutes:02d} хв"


def state_from_power(power_w: float) -> tuple[str, str]:
    if power_w > 30:
        return "charging", "Заряджається"
    if power_w < -30:
        return "discharging", "Розряджається"
    return "idle", "Увімкнена"
