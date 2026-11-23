"""Station orchestrator: polls device or simulator and builds unified state."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import date
from typing import Any

from .config import Settings, get_settings
from .estimator import TimeEstimator, state_from_power
from .events import EventLog, live_conditions
from .models import (
    BatteryState,
    DeviceControl,
    ManualSlot,
    ModeUpdate,
    OperatingMode,
    SelfDrawInfo,
    SimulatorOverride,
    StationConfigUpdate,
    StationState,
    TelemetryPoint,
)
from .prefs import DevicePrefs
from .sessions import ReserveJournal
from .simulator import SimulatorState
from .telemetry import TelemetryStore
from .udp_client import MarstekUdpClient

logger = logging.getLogger(__name__)

_MODE_BY_NAME = {mode.value.lower(): mode for mode in OperatingMode}


def _first_number(*values: Any, default: float = 0.0) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _present_number(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _opt_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "ture", "1", "yes"}
    return bool(value)


def _result(response: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("error"):
        return {}
    result = response.get("result")
    return result if isinstance(result, dict) else {}


def _command_message(response: dict[str, Any]) -> tuple[bool, str]:
    error = response.get("error")
    if isinstance(error, dict):
        if error.get("code") == -32601:
            return False, "Станція не знає цю команду. DOD, LED і клас потужності є з прошивки 150."
        return False, str(error.get("message") or "Станція відхилила команду")
    if error:
        return False, str(error)
    result = response.get("result") or {}
    if isinstance(result, dict) and "set_result" in result and _opt_bool(result.get("set_result")) is False:
        return False, "Станція не застосувала налаштування"
    return True, "Застосовано"


def _parse_mode(value: Any) -> OperatingMode | None:
    if not isinstance(value, str):
        return None
    return _MODE_BY_NAME.get(value.strip().lower())


def _kwh(value: Any, scale: float = 1.0) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value) * scale / 1000.0
    except (TypeError, ValueError):
        return None


class StationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = MarstekUdpClient(
            self.settings.marstek_ip,
            self.settings.marstek_port,
            self.settings.udp_timeout_seconds,
        )
        self.simulator = SimulatorState()
        self.prefs = DevicePrefs()
        self.events = EventLog()
        self.sessions = ReserveJournal()
        self.telemetry = TelemetryStore(
            capacity_wh=self.settings.battery_capacity_wh,
            seed_self_w=self.prefs.self_draw_w,
        )
        self.settings.min_soc_reserve_pct = float(100 - self.prefs.dod_pct)
        self.estimator = TimeEstimator(
            capacity_wh=self.settings.battery_capacity_wh,
            min_soc_reserve_pct=self.settings.min_soc_reserve_pct,
            efficiency=self.settings.inverter_efficiency,
            window_seconds=self.settings.avg_window_seconds,
            self_draw_w=self.telemetry.measured_w,
        )
        self.mode = OperatingMode.AUTO
        self.power_limit_w = 1500
        self.connected = False
        self.latency_ms: int | None = None
        self._raw: dict[str, Any] = {}
        self._cached: dict[str, Any] = {}
        self._history: deque[TelemetryPoint] = deque(maxlen=720)
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._last_state: StationState | None = None
        self._poll_n = 0
        self._daily_stamp = date.today()
        self._daily_charged_kwh = 0.0
        self._daily_discharged_kwh = 0.0
        self._last_energy_ts: float | None = None
        self._seen_online = False
        self._last_good_at: float | None = None
        self._bat: dict[str, Any] = {}
        self._es: dict[str, Any] = {}
        self._mode_info: dict[str, Any] = {}
        self._em: dict[str, Any] = {}

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        interval = self.settings.poll_interval_seconds
        while True:
            try:
                await self.refresh()
            except Exception as exc:
                logger.exception("Poll error: %s", exc)
            # Live Wi-Fi already waits between UDP queries. Demo keeps the short tick.
            pause = 0.4 if not self.settings.demo_mode else interval
            await asyncio.sleep(pause)

    async def refresh(self) -> StationState:
        async with self._lock:
            if self.settings.demo_mode:
                self.simulator.mode = self.mode.value
                self.simulator.power_limit_w = self.power_limit_w
                self.simulator.tick(self.settings.poll_interval_seconds)
                snap = self.simulator.snapshot()
                self.connected = True
                self.latency_ms = snap["latency_ms"]
                self._raw = snap
            else:
                await self._poll_device()

            state = self._build_state()
            self._last_state = state
            return state

    async def _call(self, method: str) -> dict[str, Any]:
        try:
            callers = {
                "device": self.client.get_device,
                "wifi": self.client.get_wifi_status,
                "ble": self.client.get_ble_status,
                "bat": self.client.get_battery_status,
                "es": self.client.get_es_status,
                "mode": self.client.get_es_mode,
                "em": self.client.get_em_status,
            }
            return await callers[method]()
        except Exception as exc:
            logger.debug("UDP %s failed: %s", method, exc)
            return {}

    def _remember(self, **values: Any) -> None:
        for key, value in values.items():
            if value is not None:
                self._cached[key] = value

    def _take_ct(self, source: dict[str, Any]) -> None:
        if not source:
            return
        connected = _opt_int(source.get("ct_state"))
        if connected is not None:
            self._remember(ct_connected=connected == 1)
        self._remember(
            ct_a_w=_first_number(source.get("a_power"), default=None) if source.get("a_power") is not None else None,
            ct_b_w=_first_number(source.get("b_power"), default=None) if source.get("b_power") is not None else None,
            ct_c_w=_first_number(source.get("c_power"), default=None) if source.get("c_power") is not None else None,
            ct_power_w=_first_number(source.get("total_power"), default=None) if source.get("total_power") is not None else None,
        )

    def _roll_daily(self, power: float, now: float) -> None:
        today = date.today()
        if today != self._daily_stamp:
            self._daily_stamp = today
            self._daily_charged_kwh = 0.0
            self._daily_discharged_kwh = 0.0
        if self._last_energy_ts is not None:
            dt = now - self._last_energy_ts
            if 0 < dt < 30:
                watt_hours = power * dt / 3600.0
                if watt_hours > 0:
                    self._daily_charged_kwh += watt_hours / 1000.0
                elif watt_hours < 0:
                    self._daily_discharged_kwh += abs(watt_hours) / 1000.0
        self._last_energy_ts = now

    _LIVE_CYCLE = ("es", "bat", "es", "bat", "mode", "es", "bat", "em", "es", "wifi", "es", "bat", "device", "es", "ble")

    def _mark_silence(self) -> None:
        # A missed reply is normal on Venus Wi-Fi. Keep the last reserve on screen
        # until the station has actually been quiet for a while.
        if self._last_good_at is not None and time.time() - self._last_good_at < 35:
            return
        self.connected = False
        self.latency_ms = None
        if self._raw:
            self._raw["daily_charged_kwh"] = round(self._daily_charged_kwh, 3)
            self._raw["daily_discharged_kwh"] = round(self._daily_discharged_kwh, 3)

    async def _poll_device(self) -> None:
        self._poll_n += 1
        kind = self._LIVE_CYCLE[(self._poll_n - 1) % len(self._LIVE_CYCLE)]
        resp = await self._call(kind)
        data = _result(resp)
        if not data:
            self._mark_silence()
            return

        self._last_good_at = time.time()
        self.connected = True
        self.latency_ms = resp.get("_latency_ms")
        if kind == "bat":
            self._bat = data
        elif kind == "es":
            self._es = data
        elif kind == "mode":
            self._mode_info = data
        elif kind == "em":
            self._em = data
        elif kind == "device":
            self._remember(device_model=data.get("device"), firmware=_opt_int(data.get("ver")))
            self._remember(wifi_ssid=data.get("wifi_name"))
        elif kind == "wifi":
            self._remember(wifi_ssid=data.get("ssid"), wifi_rssi=_opt_int(data.get("rssi")))
        elif kind == "ble":
            self._remember(ble_state=data.get("state"))

        self._compose_raw(resp.get("_latency_ms"))

    def _compose_raw(self, latency_ms: Any) -> None:
        bat = self._bat
        es = self._es
        mode_info = self._mode_info
        em = self._em

        soc = _first_number(bat.get("soc"), es.get("bat_soc"), mode_info.get("bat_soc"))
        temp = _first_number(bat.get("bat_temp"), default=0.0)
        remaining = bat.get("bat_capacity")
        remaining_wh = _first_number(remaining, default=0.0) if remaining is not None else 0.0
        rated = _first_number(bat.get("rated_capacity"), es.get("bat_cap"), default=0.0)
        if rated > 100:
            self.settings.battery_capacity_wh = rated
        if remaining_wh <= 0 and rated > 0:
            remaining_wh = rated * soc / 100.0

        ongrid = _first_number(es.get("ongrid_power"), mode_info.get("ongrid_power"), default=0.0)
        offgrid = _first_number(es.get("offgrid_power"), mode_info.get("offgrid_power"), default=0.0)
        solar = _first_number(es.get("pv_power"), default=0.0)
        # This firmware omits bat_power. Off-grid output is the watts the station
        # is actually giving the house; on-grid import is charge from the grid.
        reported = _present_number(es.get("bat_power"), mode_info.get("bat_power"))
        if reported is not None and abs(reported) >= 30:
            power = reported
        else:
            # Off-grid watts are the house. The station's own draw is measured separately.
            power = ongrid - offgrid

        self._take_ct(em)
        self._take_ct(mode_info)
        ct_connected = self._cached.get("ct_connected")
        ct_power = self._cached.get("ct_power_w")
        if ct_connected and ct_power is not None:
            grid = float(ct_power)
            home = max(0.0, float(ct_power) - power)
        else:
            grid = ongrid
            home = offgrid if offgrid else max(-power, 0.0)

        parsed_mode = _parse_mode(mode_info.get("mode"))
        if parsed_mode is not None:
            self.mode = parsed_mode

        now = time.time()
        self._roll_daily(power, now)
        self._remember(
            charge_allowed=_opt_bool(bat.get("charg_flag")) if bat else None,
            discharge_allowed=_opt_bool(bat.get("dischrg_flag")) if bat else None,
            rated_capacity_wh=rated if rated > 0 else None,
            total_grid_import_kwh=_kwh(es.get("total_grid_input_energy")) if es else None,
            total_grid_export_kwh=_kwh(es.get("total_grid_output_energy")) if es else None,
            total_load_kwh=_kwh(es.get("total_load_energy")) if es else None,
            total_pv_kwh=_kwh(es.get("total_pv_energy"), scale=10.0) if es else None,
        )

        self._raw = {
            "soc_pct": soc,
            "remaining_wh": remaining_wh,
            "battery_power_w": power,
            "temp_c": temp,
            "voltage_v": 0.0,
            "grid_input_w": grid,
            "solar_power_w": solar,
            "home_load_w": home,
            "daily_charged_kwh": self._daily_charged_kwh,
            "daily_discharged_kwh": self._daily_discharged_kwh,
            "latency_ms": latency_ms,
            **self._cached,
        }

    def _build_state(self, *, record: bool = True) -> StationState:
        raw = self._raw
        soc = float(raw.get("soc_pct", 0) or 0)
        power = float(raw.get("battery_power_w", 0) or 0)
        now = time.time()

        remaining_wh = float(raw.get("remaining_wh") or 0)
        if remaining_wh <= 0:
            remaining_wh = self.settings.battery_capacity_wh * (soc / 100.0)

        rated = float(raw.get("rated_capacity_wh") or self.settings.battery_capacity_wh)
        self_draw = self._sync_telemetry(
            now,
            record=record,
            power=power,
            soc=soc,
            remaining_wh=remaining_wh,
            capacity_wh=rated,
            home_w=float(raw.get("home_load_w", 0) or 0),
            grid_w=float(raw.get("grid_input_w", 0) or 0),
        )

        self.estimator.min_soc_reserve_pct = self.settings.min_soc_reserve_pct
        self.estimator.efficiency = self.settings.inverter_efficiency
        self.estimator.capacity_wh = self.settings.battery_capacity_wh
        self.estimator.self_draw_w = self.telemetry.measured_w
        if record:
            self.estimator.push(power, now)
        avg = self.estimator.average_power_w
        seconds, label, subtitle = self.estimator.estimate(soc, power)
        state_key, state_label = state_from_power(power)
        seeded = raw.get("history") if isinstance(raw.get("history"), list) else None
        if seeded:
            history = [
                TelemetryPoint(
                    ts=float(point["ts"]),
                    soc_pct=float(point.get("soc_pct") or soc),
                    power_w=float(point["power_w"]),
                )
                for point in seeded[-300:]
                if isinstance(point, dict) and "ts" in point and "power_w" in point
            ]
        else:
            if record:
                self._history.append(TelemetryPoint(ts=now, soc_pct=soc, power_w=power))
            history = list(self._history)[-180:]

        return StationState(
            connected=self.connected,
            demo_mode=self.settings.demo_mode,
            latency_ms=self.latency_ms,
            station_name=str(raw.get("device_model") or "Marstek Venus E"),
            station_ip=self.settings.marstek_ip,
            station_port=self.settings.marstek_port,
            soc_pct=round(soc, 2),
            remaining_wh=round(remaining_wh, 1),
            remaining_kwh=round(remaining_wh / 1000.0, 3),
            capacity_kwh=round(rated / 1000.0, 2),
            battery_temp_c=float(raw.get("temp_c", 0) or 0),
            battery_voltage_v=float(raw.get("voltage_v", 0) or 0),
            battery_power_w=round(power, 1),
            battery_power_avg_w=round(avg, 1),
            grid_power_w=float(raw.get("grid_input_w", 0) or 0),
            solar_power_w=float(raw.get("solar_power_w", 0) or 0),
            home_load_w=float(raw.get("home_load_w", 0) or 0),
            station_self_w=round(self_draw.watts, 1),
            station_self_source=self_draw.source,  # type: ignore[arg-type]
            self_draw=self_draw,
            state=BatteryState(state_key),
            state_label=state_label,
            time_remaining_seconds=seconds,
            time_remaining_label=label,
            time_remaining_subtitle=subtitle,
            mode=self.mode,
            power_limit_w=min(self.power_limit_w, self.prefs.power_version_w),
            passive_countdown_s=self.prefs.passive_countdown_s,
            passive_direction=self.prefs.passive_direction,  # type: ignore[arg-type]
            schedules=list(self.prefs.schedules),
            daily_charged_kwh=round(float(raw.get("daily_charged_kwh", 0) or 0), 3),
            daily_discharged_kwh=round(float(raw.get("daily_discharged_kwh", 0) or 0), 3),
            total_grid_import_kwh=round(float(raw.get("total_grid_import_kwh", 0) or 0), 2),
            total_grid_export_kwh=round(float(raw.get("total_grid_export_kwh", 0) or 0), 2),
            total_load_kwh=round(float(raw.get("total_load_kwh", 0) or 0), 2),
            total_pv_kwh=round(float(raw.get("total_pv_kwh", 0) or 0), 2),
            min_soc_reserve_pct=self.settings.min_soc_reserve_pct,
            inverter_efficiency=self.settings.inverter_efficiency,
            dod_pct=self.prefs.dod_pct,
            led_on=self.prefs.led_on,
            ble_broadcast=self.prefs.ble_broadcast,
            power_version_w=self.prefs.power_version_w,
            device_model=str(raw.get("device_model") or "Venus E"),
            firmware=_opt_int(raw.get("firmware")),
            wifi_ssid=str(raw.get("wifi_ssid") or ""),
            wifi_rssi=_opt_int(raw.get("wifi_rssi")),
            ble_state=str(raw.get("ble_state") or ""),
            charge_allowed=_opt_bool(raw.get("charge_allowed")) if "charge_allowed" in raw else None,
            discharge_allowed=_opt_bool(raw.get("discharge_allowed")) if "discharge_allowed" in raw else None,
            rated_capacity_wh=rated,
            ct_connected=raw.get("ct_connected") if isinstance(raw.get("ct_connected"), bool) else None,
            ct_power_w=float(raw.get("ct_power_w") or 0),
            ct_a_w=float(raw.get("ct_a_w") or 0),
            ct_b_w=float(raw.get("ct_b_w") or 0),
            ct_c_w=float(raw.get("ct_c_w") or 0),
            history=history,
            sessions=self._sync_sessions(
                now,
                record=record,
                power=power,
                soc=soc,
                remaining_wh=remaining_wh,
                capacity_wh=rated,
                live_forecast_seconds=seconds,
            ),
            events=self._sync_events(
                now,
                soc=soc,
                power=power,
                home_w=float(raw.get("home_load_w", 0) or 0),
                grid_w=float(raw.get("grid_input_w", 0) or 0),
                temp_c=float(raw.get("temp_c", 0) or 0),
                wifi_rssi=_opt_int(raw.get("wifi_rssi")),
                charge_allowed=_opt_bool(raw.get("charge_allowed")) if "charge_allowed" in raw else None,
                discharge_allowed=_opt_bool(raw.get("discharge_allowed")) if "discharge_allowed" in raw else None,
            ),
            updated_at=now,
        )

    def _sync_events(
        self,
        now: float,
        *,
        soc: float,
        power: float,
        home_w: float,
        grid_w: float,
        temp_c: float,
        wifi_rssi: int | None,
        charge_allowed: bool | None,
        discharge_allowed: bool | None,
    ):
        if self.connected:
            self._seen_online = True
        self.events.observe(
            now,
            live_conditions(
                connected=self.connected,
                seen_online=self._seen_online,
                home_w=home_w,
                cap_w=self.prefs.power_version_w,
                grid_w=grid_w,
                power_w=power,
                soc=soc,
                reserve=self.settings.min_soc_reserve_pct,
                temp_c=temp_c,
                wifi_rssi=wifi_rssi,
                charge_allowed=charge_allowed,
                discharge_allowed=discharge_allowed,
            ),
        )
        return self.events.recent()

    def _sync_sessions(
        self,
        now: float,
        *,
        record: bool,
        power: float,
        soc: float,
        remaining_wh: float,
        capacity_wh: float,
        live_forecast_seconds: int | None = None,
    ):
        if record:
            self.sessions.observe(
                now,
                connected=self.connected,
                power_w=power,
                soc_pct=soc,
                remaining_wh=remaining_wh,
                capacity_wh=capacity_wh,
                reserve_pct=self.settings.min_soc_reserve_pct,
                efficiency=self.settings.inverter_efficiency,
                self_draw_w=self.telemetry.measured_w,
            )
        return self.sessions.view(now, live_forecast_seconds=live_forecast_seconds)

    def _sync_telemetry(
        self,
        now: float,
        *,
        record: bool,
        power: float,
        soc: float,
        remaining_wh: float,
        capacity_wh: float,
        home_w: float,
        grid_w: float,
    ) -> SelfDrawInfo:
        if record:
            before = self.telemetry.measured_w
            self.telemetry.observe(
                now,
                connected=self.connected,
                soc_pct=soc,
                remaining_wh=remaining_wh,
                battery_power_w=power,
                home_load_w=home_w,
                grid_power_w=grid_w,
                mode=self.mode.value,
                capacity_wh=capacity_wh,
            )
            if self.telemetry.measured_w != before and self.telemetry.measured_w is not None:
                self.prefs.self_draw_w = self.telemetry.measured_w
                self.prefs.save()
        return SelfDrawInfo.model_validate(self.telemetry.report(now).model_dump())

    async def list_sessions(self):
        async with self._lock:
            return self.sessions.view(time.time(), limit=None)

    def _note_failure(self, message: str) -> None:
        if message:
            self.events.note("error", "command", "Команда не пройшла", message, time.time())

    def get_state(self) -> StationState:
        if self._last_state is None:
            return self._build_state(record=False)
        return self._last_state

    async def update_config(self, update: StationConfigUpdate) -> StationState:
        async with self._lock:
            if update.marstek_ip is not None:
                self.settings.marstek_ip = update.marstek_ip
                self.client.update_endpoint(update.marstek_ip)
            if update.marstek_port is not None:
                self.settings.marstek_port = update.marstek_port
                self.client.update_endpoint(self.settings.marstek_ip, update.marstek_port)
            if update.min_soc_reserve_pct is not None:
                self.settings.min_soc_reserve_pct = update.min_soc_reserve_pct
            if update.inverter_efficiency is not None:
                self.settings.inverter_efficiency = update.inverter_efficiency
            if update.demo_mode is not None:
                self.settings.demo_mode = update.demo_mode
                self._last_energy_ts = None
            state = self._build_state(record=False)
            self._last_state = state
            return state

    def _limit(self, watts: int) -> int:
        cap = self.prefs.power_version_w
        return max(-cap, min(cap, watts))

    def _mode_config(self, mode: OperatingMode, slot: ManualSlot | None = None) -> dict[str, Any]:
        if mode == OperatingMode.AI:
            return {"mode": "AI", "ai_cfg": {"enable": 1}}
        if mode == OperatingMode.UPS:
            return {"mode": "Ups", "ups_cfg": {"enable": 1}}
        if mode == OperatingMode.PASSIVE:
            magnitude = abs(self._limit(self.power_limit_w))
            signed = -magnitude if self.prefs.passive_direction == "charge" else magnitude
            return {
                "mode": "Passive",
                "passive_cfg": {"power": signed, "cd_time": self.prefs.passive_countdown_s},
            }
        if mode == OperatingMode.MANUAL and slot is not None:
            return {"mode": "Manual", "manual_cfg": self._slot_cfg(slot)}
        return {"mode": "Auto", "auto_cfg": {"enable": 1}}

    def _slot_cfg(self, slot: ManualSlot) -> dict[str, Any]:
        return {
            "time_num": slot.time_num,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "week_set": slot.week_set,
            "power": self._limit(slot.power_w),
            "enable": 1 if slot.enable else 0,
        }

    async def _push_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if self.settings.demo_mode:
            return True, "Застосовано в DEMO"
        try:
            response = await self.client.set_es_mode(config)
        except Exception as exc:
            logger.warning("ES.SetMode failed: %s", exc)
            return False, "Немає відповіді від станції"
        return _command_message(response)

    async def set_mode(self, update: ModeUpdate) -> tuple[bool, str, StationState]:
        async with self._lock:
            if update.power_limit_w is not None:
                self.power_limit_w = self._limit(abs(update.power_limit_w))
            if update.passive_countdown_s is not None:
                self.prefs.passive_countdown_s = update.passive_countdown_s
            if update.passive_direction is not None:
                self.prefs.passive_direction = update.passive_direction
            self.prefs.save()
            self.simulator.mode = update.mode.value
            self.simulator.power_limit_w = self.power_limit_w

            slot = self.prefs.active_slot() if update.mode == OperatingMode.MANUAL else None
            if update.mode == OperatingMode.MANUAL and slot is None and not self.settings.demo_mode:
                message = "Ручний режим вмикається вікном розкладу. Додай його в налаштуваннях."
                self._note_failure(message)
                state = self._build_state(record=False)
                self._last_state = state
                return False, message, state

            ok, message = await self._push_config(self._mode_config(update.mode, slot))
            if ok:
                self.mode = update.mode
                if update.mode == OperatingMode.MANUAL and slot is not None:
                    message = "Ручний режим і збережене вікно надіслані"
                elif update.mode == OperatingMode.PASSIVE:
                    direction = "заряд" if self.prefs.passive_direction == "charge" else "розряд"
                    message = f"Пасивний {direction} {self.power_limit_w} Вт на {self.prefs.passive_countdown_s // 60} хв"
            else:
                self._note_failure(message)
            state = self._build_state(record=False)
            self._last_state = state
            return ok, message, state

    async def apply_schedule(self, slot: ManualSlot) -> tuple[bool, str, StationState]:
        async with self._lock:
            stored = slot.model_copy(update={"power_w": self._limit(slot.power_w)})
            self.prefs.upsert_slot(stored)
            self.prefs.save()
            self.power_limit_w = abs(stored.power_w) or self.power_limit_w
            ok, message = await self._push_config({"mode": "Manual", "manual_cfg": self._slot_cfg(stored)})
            if ok:
                self.mode = OperatingMode.MANUAL
                self.simulator.mode = self.mode.value
                message = f"Вікно {stored.time_num + 1} надіслано на станцію"
            else:
                self._note_failure(message)
            state = self._build_state(record=False)
            self._last_state = state
            return ok, message, state

    async def apply_device(self, control: DeviceControl) -> tuple[bool, str, StationState]:
        async with self._lock:
            notes: list[str] = []
            ok = True

            async def _run(label: str, call: Any, remember: Any) -> None:
                nonlocal ok
                if self.settings.demo_mode:
                    remember()
                    notes.append(f"{label}: застосовано в DEMO")
                    return
                try:
                    response = await call()
                except Exception as exc:
                    logger.warning("%s failed: %s", label, exc)
                    ok = False
                    notes.append(f"{label}: немає відповіді")
                    return
                success, message = _command_message(response)
                if success:
                    remember()
                    notes.append(f"{label}: застосовано")
                else:
                    ok = False
                    notes.append(f"{label}: {message}")

            if control.dod_pct is not None:
                dod = control.dod_pct

                def _save_dod() -> None:
                    self.prefs.dod_pct = dod
                    self.settings.min_soc_reserve_pct = float(100 - dod)

                await _run("DOD", lambda: self.client.set_dod(dod), _save_dod)

            if control.led_on is not None:
                led = control.led_on
                await _run("LED", lambda: self.client.set_led(led), lambda: setattr(self.prefs, "led_on", led))

            if control.ble_broadcast is not None:
                ble = control.ble_broadcast
                await _run(
                    "Bluetooth",
                    lambda: self.client.set_ble_broadcast(ble),
                    lambda: setattr(self.prefs, "ble_broadcast", ble),
                )

            if control.power_version_w is not None:
                version = control.power_version_w

                def _save_version() -> None:
                    self.prefs.power_version_w = version
                    self.power_limit_w = min(self.power_limit_w, version)

                await _run("Потужність", lambda: self.client.set_power_version(version), _save_version)

            if notes:
                self.prefs.save()
            message = " · ".join(notes) if notes else "Немає змін"
            if not ok:
                self._note_failure(message)
            state = self._build_state(record=False)
            self._last_state = state
            return ok, message, state

    async def clear_events(self) -> StationState:
        async with self._lock:
            self.events.clear()
            state = self._build_state(record=False)
            self._last_state = state
            return state

    async def clear_sessions(self) -> StationState:
        async with self._lock:
            self.sessions.clear()
            state = self._build_state(record=False)
            self._last_state = state
            return state

    async def list_telemetry(self, hours: float = 24.0):
        async with self._lock:
            return self.telemetry.recent(hours=hours)

    async def self_draw_report(self) -> SelfDrawInfo:
        async with self._lock:
            return SelfDrawInfo.model_validate(self.telemetry.report().model_dump())

    async def apply_simulator(self, override: SimulatorOverride) -> StationState:
        async with self._lock:
            self.simulator.apply_override(
                home_load_w=override.home_load_w,
                grid_input_w=override.grid_input_w,
                soc_pct=override.soc_pct,
                battery_power_w=override.battery_power_w,
                temp_c=override.temp_c,
            )
            snap = self.simulator.snapshot()
            self._raw = snap
            self.connected = True
            self.latency_ms = snap["latency_ms"]
            state = self._build_state()
            self._last_state = state
            return state
