"""Persistent telemetry log and idle self-draw measurements.

When the station is on but not feeding the house, SOC still falls. Those quiet
stretches are the only clean way to learn how many watts the inverter eats alone.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from .estimator import station_self_w as estimate_self_w

LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "telemetry.ndjson"
IDLE_PATH = Path(__file__).resolve().parents[1] / "data" / "idle.json"
KEEP_SECONDS = 14 * 24 * 3600
SAMPLE_EVERY_S = 30.0
MAX_IDLE = 120
PAYLOAD_IDLE = 24
WINDOWS_H = (1, 2, 5, 10)

# Quiet enough that house load is not the story.
IDLE_POWER_W = 30.0
OPEN_HOLD_S = 90.0
CLOSE_BUSY_S = 45.0
GAP_CLOSE_S = 120.0
# SOC on Venus jumps in whole percents. Need a real stretch before we trust it.
MIN_MEASURE_S = 45 * 60
MIN_USED_PCT = 0.4
MIN_USED_WH = 15.0
CALIBRATE_S = 60 * 60


class TelemetrySample(BaseModel):
    ts: float
    soc_pct: float
    remaining_wh: float
    battery_power_w: float
    home_load_w: float = 0
    grid_power_w: float = 0
    mode: str = ""


class IdleStretch(BaseModel):
    """Station on, no meaningful charge/discharge to the house."""

    id: str
    started_at: float
    ended_at: float | None = None
    updated_at: float
    start_soc_pct: float
    start_wh: float
    end_soc_pct: float
    end_wh: float
    used_pct: float = 0
    used_wh: float = 0
    avg_w: float = 0
    pct_per_12h: float = 0


class DrainWindow(BaseModel):
    hours: int
    available: bool = False
    quiet: bool = False
    samples: int = 0
    start_soc_pct: float = 0
    end_soc_pct: float = 0
    used_pct: float = 0
    used_wh: float = 0
    avg_w: float = 0
    pct_per_12h: float = 0


class SelfDrawReport(BaseModel):
    watts: float
    source: str = "estimate"  # estimate | measured
    measured_at: float | None = None
    measured_hours: float | None = None
    measured_pct_per_12h: float | None = None
    idle_open: IdleStretch | None = None
    idle: list[IdleStretch] = Field(default_factory=list)
    windows: list[DrainWindow] = Field(default_factory=list)


@dataclass
class _Pending:
    since: float
    soc: float
    wh: float


class TelemetryStore:
    def __init__(
        self,
        log_path: Path = LOG_PATH,
        idle_path: Path = IDLE_PATH,
        *,
        capacity_wh: float = 5120.0,
        seed_self_w: float | None = None,
    ) -> None:
        self.log_path = log_path
        self.idle_path = idle_path
        self.capacity_wh = capacity_wh
        self.samples: list[TelemetrySample] = []
        self.idle: list[IdleStretch] = []
        self._open_id: str | None = None
        self._pending: _Pending | None = None
        self._busy_since: float | None = None
        self._last_sample_ts = 0.0
        self._last_save = 0.0
        self.measured_w: float | None = None
        self.measured_at: float | None = None
        self.measured_hours: float | None = None
        self.measured_pct_per_12h: float | None = None
        if seed_self_w is not None and seed_self_w >= 5:
            self.measured_w = float(seed_self_w)
        self.load()

    def load(self) -> None:
        self._load_log()
        self._load_idle()

    def _load_log(self) -> None:
        if not self.log_path.exists():
            return
        cutoff = time.time() - KEEP_SECONDS
        loaded: list[TelemetrySample] = []
        try:
            with self.log_path.open(encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = TelemetrySample.model_validate(json.loads(line))
                    except Exception:
                        continue
                    if item.ts >= cutoff:
                        loaded.append(item)
        except OSError:
            return
        self.samples = loaded
        if self.samples:
            self._last_sample_ts = self.samples[-1].ts
        self._rewrite_log()

    def _load_idle(self) -> None:
        try:
            data = json.loads(self.idle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        rows = data.get("idle")
        if isinstance(rows, list):
            loaded: list[IdleStretch] = []
            for item in rows:
                try:
                    loaded.append(IdleStretch.model_validate(item))
                except Exception:
                    continue
            self.idle = loaded[-MAX_IDLE:]
        open_rows = [row for row in self.idle if row.ended_at is None]
        open_rows.sort(key=lambda row: row.started_at)
        for stale in open_rows[:-1]:
            stale.ended_at = stale.updated_at
        if open_rows:
            self._open_id = open_rows[-1].id
        measured = data.get("measured_w")
        if isinstance(measured, (int, float)) and measured >= 5:
            self.measured_w = float(measured)
            self.measured_at = float(data["measured_at"]) if data.get("measured_at") else None
            self.measured_hours = float(data["measured_hours"]) if data.get("measured_hours") else None
            self.measured_pct_per_12h = (
                float(data["measured_pct_per_12h"]) if data.get("measured_pct_per_12h") else None
            )

    def _rewrite_log(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w", encoding="utf-8") as handle:
            for sample in self.samples:
                handle.write(sample.model_dump_json())
                handle.write("\n")

    def _save_idle(self) -> None:
        self.idle_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "measured_w": self.measured_w,
            "measured_at": self.measured_at,
            "measured_hours": self.measured_hours,
            "measured_pct_per_12h": self.measured_pct_per_12h,
            "idle": [row.model_dump() for row in self.idle[-MAX_IDLE:]],
        }
        self.idle_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.samples.clear()
        self.idle.clear()
        self._open_id = None
        self._pending = None
        self._busy_since = None
        self.measured_w = None
        self.measured_at = None
        self.measured_hours = None
        self.measured_pct_per_12h = None
        self._rewrite_log()
        self._save_idle()

    def watts(self) -> float:
        if self.measured_w is not None and self.measured_w >= 5:
            return self.measured_w
        return estimate_self_w(self.capacity_wh)

    def source(self) -> str:
        return "measured" if self.measured_w is not None and self.measured_w >= 5 else "estimate"

    def observe(
        self,
        now: float,
        *,
        connected: bool,
        soc_pct: float,
        remaining_wh: float,
        battery_power_w: float,
        home_load_w: float,
        grid_power_w: float,
        mode: str,
        capacity_wh: float,
    ) -> None:
        if capacity_wh > 0:
            self.capacity_wh = capacity_wh
        if not connected:
            if self._open_id and self._last_sample_ts and now - self._last_sample_ts >= GAP_CLOSE_S:
                self._close_idle(self._last_sample_ts)
            self._pending = None
            return

        quiet = abs(battery_power_w) < IDLE_POWER_W
        self._track_idle(now, quiet=quiet, soc_pct=soc_pct, remaining_wh=remaining_wh)

        if now - self._last_sample_ts >= SAMPLE_EVERY_S or not self.samples:
            sample = TelemetrySample(
                ts=now,
                soc_pct=round(soc_pct, 2),
                remaining_wh=round(remaining_wh, 1),
                battery_power_w=round(battery_power_w, 1),
                home_load_w=round(home_load_w, 1),
                grid_power_w=round(grid_power_w, 1),
                mode=mode,
            )
            self.samples.append(sample)
            self._last_sample_ts = now
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(sample.model_dump_json())
                handle.write("\n")
            cutoff = now - KEEP_SECONDS
            if self.samples and self.samples[0].ts < cutoff:
                self.samples = [row for row in self.samples if row.ts >= cutoff]
                self._rewrite_log()

        if now - self._last_save >= 20:
            self._save_idle()
            self._last_save = now

    def report(self, now: float | None = None) -> SelfDrawReport:
        stamp = now if now is not None else time.time()
        idle_view = [self._decorate(row, stamp) for row in self._ordered_idle()]
        open_idle = next((row for row in idle_view if row.ended_at is None), None)
        return SelfDrawReport(
            watts=round(self.watts(), 1),
            source=self.source(),
            measured_at=self.measured_at,
            measured_hours=self.measured_hours,
            measured_pct_per_12h=self.measured_pct_per_12h,
            idle_open=open_idle,
            idle=idle_view[:PAYLOAD_IDLE],
            windows=self.windows(stamp),
        )

    def recent(self, hours: float = 24.0, limit: int = 4000) -> list[TelemetrySample]:
        cutoff = time.time() - hours * 3600
        rows = [row for row in self.samples if row.ts >= cutoff]
        if len(rows) <= limit:
            return rows
        step = max(1, len(rows) // limit)
        return rows[::step][:limit]

    def windows(self, now: float) -> list[DrainWindow]:
        out: list[DrainWindow] = []
        for hours in WINDOWS_H:
            out.append(self._window(now, hours))
        return out

    def _window(self, now: float, hours: int) -> DrainWindow:
        start_ts = now - hours * 3600
        rows = [row for row in self.samples if start_ts <= row.ts <= now]
        if len(rows) < 3:
            return DrainWindow(hours=hours)
        first = rows[0]
        last = rows[-1]
        span_h = max(1 / 3600, (last.ts - first.ts) / 3600)
        # Need most of the requested window on disk, otherwise "5 год" is just a short stretch.
        if span_h < hours * 0.7:
            return DrainWindow(hours=hours, samples=len(rows))
        used_pct = max(0.0, first.soc_pct - last.soc_pct)
        used_wh = max(0.0, first.remaining_wh - last.remaining_wh)
        if used_wh < 1 and used_pct > 0 and self.capacity_wh > 0:
            used_wh = used_pct / 100.0 * self.capacity_wh
        avg_w = used_wh / span_h if span_h > 0 else 0.0
        busy = sum(1 for row in rows if abs(row.battery_power_w) >= IDLE_POWER_W)
        quiet = busy / len(rows) <= 0.12
        return DrainWindow(
            hours=hours,
            available=True,
            quiet=quiet,
            samples=len(rows),
            start_soc_pct=round(first.soc_pct, 2),
            end_soc_pct=round(last.soc_pct, 2),
            used_pct=round(used_pct, 2),
            used_wh=round(used_wh, 1),
            avg_w=round(avg_w, 1),
            pct_per_12h=round(used_pct / span_h * 12.0, 2) if span_h > 0 else 0.0,
        )

    def _track_idle(self, now: float, *, quiet: bool, soc_pct: float, remaining_wh: float) -> None:
        current = self._find(self._open_id or "")
        if current is not None:
            current.end_soc_pct = round(soc_pct, 2)
            current.end_wh = round(remaining_wh, 1)
            current.updated_at = now
            if quiet:
                self._busy_since = None
                return
            if self._busy_since is None:
                self._busy_since = now
                return
            if now - self._busy_since >= CLOSE_BUSY_S:
                self._close_idle(self._busy_since)
            return

        if quiet:
            if self._pending is None:
                self._pending = _Pending(since=now, soc=soc_pct, wh=remaining_wh)
                return
            if now - self._pending.since >= OPEN_HOLD_S:
                self._open_idle(now, soc_pct, remaining_wh)
            return
        self._pending = None

    def _open_idle(self, now: float, soc_pct: float, remaining_wh: float) -> None:
        pending = self._pending
        started = pending.since if pending else now
        stretch = IdleStretch(
            id=uuid.uuid4().hex[:10],
            started_at=started,
            updated_at=now,
            start_soc_pct=round(pending.soc if pending else soc_pct, 2),
            start_wh=round(pending.wh if pending else remaining_wh, 1),
            end_soc_pct=round(soc_pct, 2),
            end_wh=round(remaining_wh, 1),
        )
        self.idle.append(stretch)
        self._open_id = stretch.id
        self._pending = None
        self._busy_since = None
        self._trim_idle()
        self._save_idle()
        self._last_save = now

    def _close_idle(self, at: float) -> None:
        stretch = self._find(self._open_id or "")
        self._open_id = None
        self._busy_since = None
        self._pending = None
        if stretch is None:
            return
        stretch.ended_at = at
        stretch.updated_at = at
        stats = self._stats(stretch, at)
        stretch.used_pct = stats["used_pct"]
        stretch.used_wh = stats["used_wh"]
        stretch.avg_w = stats["avg_w"]
        stretch.pct_per_12h = stats["pct_per_12h"]
        elapsed = at - stretch.started_at
        if elapsed < MIN_MEASURE_S or (stretch.used_pct < MIN_USED_PCT and stretch.used_wh < MIN_USED_WH):
            self.idle = [row for row in self.idle if row.id != stretch.id]
        else:
            self._calibrate(stretch, at)
        self._save_idle()
        self._last_save = at

    def _calibrate(self, stretch: IdleStretch, at: float) -> None:
        elapsed = at - stretch.started_at
        if elapsed < CALIBRATE_S or stretch.avg_w < 5:
            return
        # Prefer the longest quiet stretches. A short hour can still bump a weak guess.
        weight = min(1.0, elapsed / (6 * 3600))
        if self.measured_w is None:
            self.measured_w = stretch.avg_w
        else:
            self.measured_w = self.measured_w * (1 - weight) + stretch.avg_w * weight
        self.measured_at = at
        self.measured_hours = round(elapsed / 3600.0, 2)
        self.measured_pct_per_12h = stretch.pct_per_12h

    def _decorate(self, stretch: IdleStretch, now: float) -> IdleStretch:
        row = stretch.model_copy()
        end = stretch.ended_at if stretch.ended_at is not None else now
        stats = self._stats(stretch, end)
        row.used_pct = stats["used_pct"]
        row.used_wh = stats["used_wh"]
        row.avg_w = stats["avg_w"]
        row.pct_per_12h = stats["pct_per_12h"]
        return row

    def _stats(self, stretch: IdleStretch, end: float) -> dict[str, float]:
        hours = max(1 / 3600, (end - stretch.started_at) / 3600)
        used_pct = max(0.0, stretch.start_soc_pct - stretch.end_soc_pct)
        used_wh = max(0.0, stretch.start_wh - stretch.end_wh)
        if used_wh < 1 and used_pct > 0 and self.capacity_wh > 0:
            used_wh = used_pct / 100.0 * self.capacity_wh
        avg_w = used_wh / hours
        return {
            "used_pct": round(used_pct, 2),
            "used_wh": round(used_wh, 1),
            "avg_w": round(avg_w, 1),
            "pct_per_12h": round(used_pct / hours * 12.0, 2),
        }

    def _ordered_idle(self) -> list[IdleStretch]:
        return sorted(self.idle, key=lambda row: (row.ended_at is not None, -row.started_at))

    def _find(self, stretch_id: str) -> IdleStretch | None:
        if not stretch_id:
            return None
        for row in reversed(self.idle):
            if row.id == stretch_id:
                return row
        return None

    def _trim_idle(self) -> None:
        if len(self.idle) <= MAX_IDLE:
            return
        open_ids = {self._open_id} if self._open_id else set()
        closed = [row for row in self.idle if row.id not in open_ids]
        opened = [row for row in self.idle if row.id in open_ids]
        room = max(0, MAX_IDLE - len(opened))
        self.idle = closed[-room:] + opened
        self.idle.sort(key=lambda row: row.started_at)
