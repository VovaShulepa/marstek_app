"""Shared Pydantic models for API and WebSocket payloads."""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
POWER_VERSIONS = (800, 1200, 1500, 2200, 2500)


class OperatingMode(str, Enum):
    AUTO = "Auto"
    AI = "AI"
    MANUAL = "Manual"
    PASSIVE = "Passive"
    UPS = "Ups"


class BatteryState(str, Enum):
    CHARGING = "charging"
    DISCHARGING = "discharging"
    IDLE = "idle"


class StationConfigUpdate(BaseModel):
    marstek_ip: Optional[str] = None
    marstek_port: Optional[int] = Field(default=None, ge=1, le=65535)
    min_soc_reserve_pct: Optional[float] = Field(default=None, ge=0, le=70)
    inverter_efficiency: Optional[float] = Field(default=None, ge=0.5, le=1.0)
    demo_mode: Optional[bool] = None


class ModeUpdate(BaseModel):
    mode: OperatingMode
    power_limit_w: Optional[int] = Field(default=None, ge=0, le=2500)
    passive_countdown_s: Optional[int] = Field(default=None, ge=0, le=86400)
    passive_direction: Optional[Literal["charge", "discharge"]] = None


class ManualSlot(BaseModel):
    time_num: int = Field(ge=0, le=9)
    start_time: str
    end_time: str
    week_set: int = Field(ge=0, le=127)
    power_w: int = Field(ge=-2500, le=2500)
    enable: bool = True

    @field_validator("start_time", "end_time")
    @classmethod
    def _clock(cls, value: str) -> str:
        if not _CLOCK.fullmatch(value):
            raise ValueError("Час має бути у форматі ГГ:ХХ")
        return value


class DeviceControl(BaseModel):
    dod_pct: Optional[int] = Field(default=None, ge=30, le=88)
    led_on: Optional[bool] = None
    ble_broadcast: Optional[bool] = None
    power_version_w: Optional[int] = None

    @field_validator("power_version_w")
    @classmethod
    def _power_class(cls, value: int | None) -> int | None:
        if value is not None and value not in POWER_VERSIONS:
            raise ValueError("Клас потужності: 800, 1200, 1500, 2200 або 2500")
        return value


class SimulatorOverride(BaseModel):
    home_load_w: Optional[float] = Field(default=None, ge=0, le=10000)
    grid_input_w: Optional[float] = Field(default=None, ge=0, le=10000)
    soc_pct: Optional[float] = Field(default=None, ge=0, le=100)
    battery_power_w: Optional[float] = Field(default=None, ge=-5000, le=5000)
    temp_c: Optional[float] = Field(default=None, ge=-20, le=80)


class TelemetryPoint(BaseModel):
    ts: float
    soc_pct: float
    power_w: float


class StationEvent(BaseModel):
    id: str
    ts: float
    ended_at: Optional[float] = None
    level: Literal["info", "warning", "error"]
    code: str
    title: str
    detail: str = ""


class ReserveSession(BaseModel):
    """One stretch of the station feeding the house from the battery."""

    id: str
    started_at: float
    ended_at: Optional[float] = None
    updated_at: float
    start_soc_pct: float
    start_wh: float
    end_soc_pct: float
    end_wh: float
    delivered_wh: float = 0
    used_pct: float = 0
    used_wh: float = 0
    avg_w: float = 0
    forecast_seconds: Optional[int] = None


class IdleStretch(BaseModel):
    id: str
    started_at: float
    ended_at: Optional[float] = None
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


class SelfDrawInfo(BaseModel):
    watts: float
    source: Literal["estimate", "measured"] = "estimate"
    measured_at: Optional[float] = None
    measured_hours: Optional[float] = None
    measured_pct_per_12h: Optional[float] = None
    idle_open: Optional[IdleStretch] = None
    idle: List[IdleStretch] = Field(default_factory=list)
    windows: List[DrainWindow] = Field(default_factory=list)


class StationState(BaseModel):
    connected: bool
    demo_mode: bool
    latency_ms: Optional[int] = None
    station_name: str = "Marstek Venus E"
    station_ip: str
    station_port: int

    soc_pct: float
    remaining_wh: float
    remaining_kwh: float
    capacity_kwh: float = 5.12
    battery_temp_c: float
    battery_voltage_v: float

    # Positive = charging into battery, negative = discharging
    battery_power_w: float
    battery_power_avg_w: float
    grid_power_w: float
    solar_power_w: float
    home_load_w: float
    station_self_w: float = 10
    station_self_source: Literal["estimate", "measured"] = "estimate"
    self_draw: Optional[SelfDrawInfo] = None

    state: BatteryState
    state_label: str
    time_remaining_seconds: Optional[int] = None
    time_remaining_label: str
    time_remaining_subtitle: str

    mode: OperatingMode
    power_limit_w: int
    passive_countdown_s: int = 300
    passive_direction: Literal["charge", "discharge"] = "discharge"
    schedules: List[ManualSlot] = Field(default_factory=list)

    daily_charged_kwh: float
    daily_discharged_kwh: float
    total_grid_import_kwh: float = 0
    total_grid_export_kwh: float = 0
    total_load_kwh: float = 0
    total_pv_kwh: float = 0

    min_soc_reserve_pct: float
    inverter_efficiency: float
    dod_pct: int = 88
    led_on: Optional[bool] = None
    ble_broadcast: Optional[bool] = None
    power_version_w: int = 2500

    device_model: str = "Venus E"
    firmware: Optional[int] = None
    wifi_ssid: str = ""
    wifi_rssi: Optional[int] = None
    ble_state: str = ""
    charge_allowed: Optional[bool] = None
    discharge_allowed: Optional[bool] = None
    rated_capacity_wh: float = 5120

    ct_connected: Optional[bool] = None
    ct_power_w: float = 0
    ct_a_w: float = 0
    ct_b_w: float = 0
    ct_c_w: float = 0

    history: List[TelemetryPoint] = Field(default_factory=list)
    events: List[StationEvent] = Field(default_factory=list)
    sessions: List[ReserveSession] = Field(default_factory=list)
    updated_at: float


class ApiResponse(BaseModel):
    ok: bool
    message: str = ""
    state: Optional[StationState] = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    demo_mode: bool
    connected: bool
