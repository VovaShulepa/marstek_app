"""Local warning journal. The Venus UDP API has no alarm feed, so the bridge
notices risky states itself and keeps a history on disk."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .models import StationEvent

EVENTS_PATH = Path(__file__).resolve().parents[1] / "data" / "events.json"
MAX_EVENTS = 180
PAYLOAD_LIMIT = 40


@dataclass
class LiveCondition:
    code: str
    level: str
    title: str
    detail: str
    hold_s: float = 8.0
    clear_s: float = 16.0


class EventLog:
    def __init__(self, path: Path = EVENTS_PATH) -> None:
        self.path = path
        self.events: list[StationEvent] = []
        self._open: dict[str, str] = {}
        self._armed: dict[str, float] = {}
        self._quiet: dict[str, float] = {}
        self._clear_s: dict[str, float] = {}
        self._last_save = 0.0
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rows = data.get("events") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return
        loaded: list[StationEvent] = []
        for item in rows:
            try:
                loaded.append(StationEvent.model_validate(item))
            except Exception:
                continue
        self.events = loaded[-MAX_EVENTS:]
        self._open = {}
        for event in self.events:
            if event.ended_at is None:
                self._open[event.code] = event.id

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"events": [event.model_dump() for event in self.events[-MAX_EVENTS:]]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def recent(self, limit: int = PAYLOAD_LIMIT) -> list[StationEvent]:
        ordered = sorted(self.events, key=lambda event: (event.ended_at is not None, -event.ts))
        return ordered[:limit]

    def note(self, level: str, code: str, title: str, detail: str, now: float) -> None:
        for event in reversed(self.events[-8:]):
            if event.code == code and event.detail == detail and now - event.ts < 90:
                return
        self.events.append(
            StationEvent(
                id=uuid.uuid4().hex[:10],
                ts=now,
                ended_at=now,
                level=level,  # type: ignore[arg-type]
                code=code,
                title=title,
                detail=detail,
            )
        )
        self._trim()
        self.save()

    def clear(self) -> None:
        self.events.clear()
        self._open.clear()
        self._armed.clear()
        self._quiet.clear()
        self._clear_s.clear()
        self.save()

    def observe(self, now: float, conditions: list[LiveCondition]) -> None:
        by_code = {item.code: item for item in conditions}
        structural = False
        for code, cond in by_code.items():
            self._quiet.pop(code, None)
            open_id = self._open.get(code)
            if open_id:
                event = self._find(open_id)
                if event and (event.detail != cond.detail or event.level != cond.level or event.title != cond.title):
                    event.detail = cond.detail
                    event.level = cond.level  # type: ignore[assignment]
                    event.title = cond.title
                self._clear_s[code] = cond.clear_s
                continue
            since = self._armed.get(code)
            if since is None:
                self._armed[code] = now
                continue
            if now - since >= cond.hold_s:
                self._open_new(cond, now)
                structural = True
        for code in list(self._open):
            if code in by_code:
                continue
            self._armed.pop(code, None)
            quiet_since = self._quiet.get(code)
            if quiet_since is None:
                self._quiet[code] = now
                continue
            if now - quiet_since >= self._clear_s.get(code, 16.0):
                self._close(code, now)
                structural = True
        if structural or (self.events and now - self._last_save >= 20):
            self.save()
            self._last_save = now

    def _open_new(self, cond: LiveCondition, now: float) -> None:
        event = StationEvent(
            id=uuid.uuid4().hex[:10],
            ts=now,
            level=cond.level,  # type: ignore[arg-type]
            code=cond.code,
            title=cond.title,
            detail=cond.detail,
        )
        self.events.append(event)
        self._open[cond.code] = event.id
        self._armed.pop(cond.code, None)
        self._clear_s[cond.code] = cond.clear_s
        self._trim()

    def _close(self, code: str, now: float) -> None:
        event = self._find(self._open.get(code, ""))
        if event and event.ended_at is None:
            event.ended_at = now
        self._open.pop(code, None)
        self._quiet.pop(code, None)
        self._clear_s.pop(code, None)

    def _find(self, event_id: str) -> StationEvent | None:
        for event in reversed(self.events):
            if event.id == event_id:
                return event
        return None

    def _trim(self) -> None:
        if len(self.events) <= MAX_EVENTS:
            return
        open_ids = set(self._open.values())
        closed = [event for event in self.events if event.id not in open_ids]
        opened = [event for event in self.events if event.id in open_ids]
        room = max(0, MAX_EVENTS - len(opened))
        self.events = closed[-room:] + opened
        self.events.sort(key=lambda event: event.ts)


def live_conditions(
    *,
    connected: bool,
    seen_online: bool,
    home_w: float,
    cap_w: int,
    grid_w: float,
    power_w: float,
    soc: float,
    reserve: float,
    temp_c: float,
    wifi_rssi: int | None,
    charge_allowed: bool | None,
    discharge_allowed: bool | None,
) -> list[LiveCondition]:
    if seen_online and not connected:
        return [
            LiveCondition(
                "offline",
                "error",
                "Немає зв'язку",
                "Станція мовчить уже пів хвилини. Цифри на екрані старі.",
                hold_s=8,
                clear_s=6,
            )
        ]
    if not connected:
        return []

    found: list[LiveCondition] = []
    maxed = cap_w > 0 and power_w <= -(cap_w * 0.9) and grid_w >= 400
    if cap_w > 0 and ((home_w >= cap_w and home_w >= 100) or maxed):
        if home_w >= 100:
            detail = f"Дім бере {round(home_w)} Вт, станція віддає до {cap_w} Вт."
            if grid_w > 80:
                detail += f" З мережі ще {round(grid_w)} Вт."
        else:
            detail = f"Станція вже на межі {cap_w} Вт, з мережі ще {round(grid_w)} Вт."
        found.append(LiveCondition("high_load", "warning", "Забагато споживання", detail, hold_s=8, clear_s=16))

    if soc <= reserve + 0.6:
        found.append(
            LiveCondition(
                "soc_reserve",
                "error",
                "Заряд на резерві",
                f"Залишилось {soc:.0f}%. Нижче резерву {reserve:.0f}% станція розряд не веде.",
                hold_s=6,
                clear_s=20,
            )
        )
    elif soc <= reserve + 8 and power_w < -40:
        found.append(
            LiveCondition(
                "soc_low",
                "warning",
                "Заряд майже на резерві",
                f"Залишилось {soc:.0f}%, резерв {reserve:.0f}%.",
                hold_s=12,
                clear_s=20,
            )
        )

    if temp_c >= 55:
        found.append(
            LiveCondition(
                "temp_critical",
                "error",
                "Перегрів батареї",
                f"Температура {temp_c:.0f}°. Зменш навантаження.",
                hold_s=10,
                clear_s=30,
            )
        )
    elif temp_c >= 45:
        found.append(
            LiveCondition(
                "temp_high",
                "warning",
                "Батарея гаряча",
                f"Температура {temp_c:.0f}°.",
                hold_s=15,
                clear_s=30,
            )
        )

    if wifi_rssi is not None and wifi_rssi < 0 and wifi_rssi <= -78:
        found.append(
            LiveCondition(
                "weak_wifi",
                "warning",
                "Слабкий Wi‑Fi",
                f"Сигнал {wifi_rssi} дБм. Команди можуть губитися.",
                hold_s=20,
                clear_s=30,
            )
        )

    if discharge_allowed is False and soc > reserve + 2:
        found.append(
            LiveCondition(
                "discharge_blocked",
                "warning",
                "Розряд зупинено",
                "Станція не дозволяє віддавати енергію в дім.",
                hold_s=8,
                clear_s=12,
            )
        )
    if charge_allowed is False and soc < 97:
        found.append(
            LiveCondition(
                "charge_blocked",
                "warning",
                "Заряд зупинено",
                "Станція не приймає енергію в батарею.",
                hold_s=8,
                clear_s=12,
            )
        )
    return found
