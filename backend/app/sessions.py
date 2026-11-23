"""Journal of reserve sessions: each stretch the station powers the house."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from .estimator import station_self_w
from .models import ReserveSession

SESSIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "sessions.json"
MAX_SESSIONS = 400
PAYLOAD_LIMIT = 16

# A fridge click is not a session. Real backup draw has to hold, then stay quiet to end.
OPEN_HOLD_S = 12.0
CLOSE_QUIET_S = 45.0
CHARGE_CLOSE_S = 18.0
GAP_CLOSE_S = 90.0
OFFLINE_CLOSE_S = 40.0
DISCHARGE_W = -50.0
IDLE_W = -30.0
INTEGRATE_W = -15.0
MAX_STEP_S = 30.0
MIN_KEEP_S = 60.0
MIN_KEEP_WH = 8.0


class ReserveJournal:
    def __init__(self, path: Path = SESSIONS_PATH) -> None:
        self.path = path
        self.sessions: list[ReserveSession] = []
        self._open_id: str | None = None
        self._pending_since: float | None = None
        self._pending_soc = 0.0
        self._pending_wh = 0.0
        self._quiet_since: float | None = None
        self._last_ts: float | None = None
        self._last_power = 0.0
        self._last_save = 0.0
        self._capacity_wh = 5120.0
        self._reserve_pct = 12.0
        self._efficiency = 0.95
        self._self_draw_w: float | None = None
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rows = data.get("sessions") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return
        loaded: list[ReserveSession] = []
        for item in rows:
            try:
                loaded.append(ReserveSession.model_validate(item))
            except Exception:
                continue
        self.sessions = loaded[-MAX_SESSIONS:]
        open_rows = [row for row in self.sessions if row.ended_at is None]
        open_rows.sort(key=lambda row: row.started_at)
        for stale in open_rows[:-1]:
            stale.ended_at = stale.updated_at
        if open_rows:
            current = open_rows[-1]
            self._open_id = current.id
            self._last_ts = current.updated_at

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sessions": [row.model_dump() for row in self.sessions[-MAX_SESSIONS:]]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.sessions.clear()
        self._open_id = None
        self._pending_since = None
        self._quiet_since = None
        self._last_ts = None
        self._last_power = 0.0
        self.save()

    def observe(
        self,
        now: float,
        *,
        connected: bool,
        power_w: float,
        soc_pct: float,
        remaining_wh: float,
        capacity_wh: float,
        reserve_pct: float,
        efficiency: float,
        self_draw_w: float | None = None,
    ) -> None:
        if capacity_wh > 0:
            self._capacity_wh = capacity_wh
        self._reserve_pct = reserve_pct
        self._efficiency = efficiency
        self._self_draw_w = self_draw_w

        if self._open_id and self._last_ts is not None:
            gap = now - self._last_ts
            stalled = gap > GAP_CLOSE_S or (not connected and gap >= OFFLINE_CLOSE_S)
            if stalled:
                self._close(self._last_ts)
                self._last_ts = None
                self._last_power = 0.0

        if not connected:
            self._pending_since = None
            return

        self._track(now, power_w, soc_pct, remaining_wh)
        self._last_ts = now
        self._last_power = power_w
        if now - self._last_save >= 15:
            self.save()
            self._last_save = now

    def view(
        self,
        now: float,
        *,
        limit: int | None = PAYLOAD_LIMIT,
        live_forecast_seconds: int | None = None,
    ) -> list[ReserveSession]:
        ordered = sorted(
            self.sessions,
            key=lambda row: (row.ended_at is not None, -row.started_at),
        )
        rows = ordered if limit is None else ordered[:limit]
        return [self._decorate(row, now, live_forecast_seconds=live_forecast_seconds) for row in rows]

    def _track(self, now: float, power_w: float, soc_pct: float, remaining_wh: float) -> None:
        session = self._find(self._open_id or "")
        if session is not None:
            self._integrate(session, now)
            session.end_soc_pct = round(soc_pct, 2)
            session.end_wh = round(remaining_wh, 1)
            session.updated_at = now
            if power_w <= IDLE_W:
                self._quiet_since = None
                return
            if self._quiet_since is None:
                self._quiet_since = now
            limit = CHARGE_CLOSE_S if power_w > 40 else CLOSE_QUIET_S
            if now - self._quiet_since >= limit:
                self._close(self._quiet_since)
            return

        if power_w <= DISCHARGE_W:
            if self._pending_since is None:
                self._pending_since = now
                self._pending_soc = soc_pct
                self._pending_wh = remaining_wh
                return
            if now - self._pending_since >= OPEN_HOLD_S:
                self._open(now, soc_pct, remaining_wh)
            return
        self._pending_since = None

    def _integrate(self, session: ReserveSession, now: float) -> None:
        if self._last_ts is None:
            return
        dt = now - self._last_ts
        if 0 < dt <= MAX_STEP_S and self._last_power <= INTEGRATE_W:
            session.delivered_wh += abs(self._last_power) * dt / 3600.0

    def _open(self, now: float, soc_pct: float, remaining_wh: float) -> None:
        started = self._pending_since or now
        session = ReserveSession(
            id=uuid.uuid4().hex[:10],
            started_at=started,
            updated_at=now,
            start_soc_pct=round(self._pending_soc, 2),
            start_wh=round(self._pending_wh, 1),
            end_soc_pct=round(soc_pct, 2),
            end_wh=round(remaining_wh, 1),
        )
        self._integrate(session, now)
        self.sessions.append(session)
        self._open_id = session.id
        self._pending_since = None
        self._quiet_since = None
        self._trim()
        self.save()
        self._last_save = now

    def _close(self, at: float) -> None:
        session = self._find(self._open_id or "")
        self._open_id = None
        self._quiet_since = None
        self._pending_since = None
        if session is None:
            return
        session.ended_at = at
        session.updated_at = at
        elapsed = at - session.started_at
        if elapsed < MIN_KEEP_S and session.delivered_wh < MIN_KEEP_WH:
            self.sessions = [row for row in self.sessions if row.id != session.id]
        self.save()
        self._last_save = at

    def _decorate(
        self,
        session: ReserveSession,
        now: float,
        *,
        live_forecast_seconds: int | None = None,
    ) -> ReserveSession:
        row = session.model_copy()
        end = session.ended_at if session.ended_at is not None else now
        elapsed = max(0.0, end - session.started_at)
        soc_pct = max(0.0, session.start_soc_pct - session.end_soc_pct)
        soc_wh = max(0.0, session.start_wh - session.end_wh)
        meter_wh = session.delivered_wh / max(self._efficiency, 0.05)
        if soc_pct >= 0.4 or soc_wh >= 20:
            used_pct = soc_pct
            used_wh = soc_wh if soc_wh > 0 else soc_pct / 100.0 * self._capacity_wh
        else:
            used_wh = meter_wh
            used_pct = (used_wh / self._capacity_wh * 100.0) if self._capacity_wh > 0 else soc_pct

        hours = elapsed / 3600.0
        avg_w = 0.0
        if hours > 0 and session.delivered_wh >= 0.3:
            avg_w = session.delivered_wh / hours
        elif hours > 0 and used_wh >= 0.3:
            avg_w = used_wh * max(self._efficiency, 0.05) / hours

        # Open session: same live estimate as the main battery card.
        # Closed session: keep a session-average fallback for history if needed.
        forecast: int | None = None
        if session.ended_at is None:
            forecast = live_forecast_seconds
        elif elapsed >= 45 and avg_w >= 25:
            reserve_wh = self._capacity_wh * (self._reserve_pct / 100.0)
            avail = max(0.0, session.end_wh - reserve_wh)
            draw = avg_w / max(self._efficiency, 0.05) + station_self_w(
                self._capacity_wh, self._self_draw_w
            )
            forecast = int(min(240 * 3600, avail / draw * 3600)) if draw > 1 else 0

        row.used_pct = round(used_pct, 2)
        row.used_wh = round(used_wh, 1)
        row.avg_w = round(avg_w, 1)
        row.forecast_seconds = forecast
        return row

    def _find(self, session_id: str) -> ReserveSession | None:
        if not session_id:
            return None
        for session in reversed(self.sessions):
            if session.id == session_id:
                return session
        return None

    def _trim(self) -> None:
        if len(self.sessions) <= MAX_SESSIONS:
            return
        open_ids = {self._open_id} if self._open_id else set()
        closed = [row for row in self.sessions if row.id not in open_ids]
        opened = [row for row in self.sessions if row.id in open_ids]
        room = max(0, MAX_SESSIONS - len(opened))
        self.sessions = closed[-room:] + opened
        self.sessions.sort(key=lambda row: row.started_at)
