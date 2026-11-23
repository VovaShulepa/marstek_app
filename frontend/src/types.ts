export type BatteryState = 'charging' | 'discharging' | 'idle'
export type OperatingMode = 'Auto' | 'AI' | 'Manual' | 'Passive' | 'Ups'
export type PassiveDirection = 'charge' | 'discharge'

export interface ManualSlot {
  time_num: number
  start_time: string
  end_time: string
  week_set: number
  power_w: number
  enable: boolean
}

export interface DiscoveredDevice {
  model: string
  firmware: number | null
  ip: string
  wifi_mac: string
  ssid: string
}

export interface TelemetryPoint {
  ts: number
  soc_pct: number
  power_w: number
}

export type EventLevel = 'info' | 'warning' | 'error'

export interface StationEvent {
  id: string
  ts: number
  ended_at: number | null
  level: EventLevel
  code: string
  title: string
  detail: string
}

export interface ReserveSession {
  id: string
  started_at: number
  ended_at: number | null
  updated_at: number
  start_soc_pct: number
  start_wh: number
  end_soc_pct: number
  end_wh: number
  delivered_wh: number
  used_pct: number
  used_wh: number
  avg_w: number
  forecast_seconds: number | null
}

export interface IdleStretch {
  id: string
  started_at: number
  ended_at: number | null
  updated_at: number
  start_soc_pct: number
  start_wh: number
  end_soc_pct: number
  end_wh: number
  used_pct: number
  used_wh: number
  avg_w: number
  pct_per_12h: number
}

export interface DrainWindow {
  hours: number
  available: boolean
  quiet: boolean
  samples: number
  start_soc_pct: number
  end_soc_pct: number
  used_pct: number
  used_wh: number
  avg_w: number
  pct_per_12h: number
}

export interface SelfDrawInfo {
  watts: number
  source: 'estimate' | 'measured'
  measured_at: number | null
  measured_hours: number | null
  measured_pct_per_12h: number | null
  idle_open: IdleStretch | null
  idle: IdleStretch[]
  windows: DrainWindow[]
}

export interface StationState {
  connected: boolean
  demo_mode: boolean
  latency_ms: number | null
  station_name: string
  station_ip: string
  station_port: number
  soc_pct: number
  remaining_wh: number
  remaining_kwh: number
  capacity_kwh: number
  battery_temp_c: number
  battery_voltage_v: number
  battery_power_w: number
  battery_power_avg_w: number
  grid_power_w: number
  solar_power_w: number
  home_load_w: number
  station_self_w?: number
  station_self_source?: 'estimate' | 'measured'
  self_draw?: SelfDrawInfo | null
  state: BatteryState
  state_label: string
  time_remaining_seconds: number | null
  time_remaining_label: string
  time_remaining_subtitle: string
  mode: OperatingMode
  power_limit_w: number
  passive_countdown_s: number
  passive_direction: PassiveDirection
  schedules: ManualSlot[]
  daily_charged_kwh: number
  daily_discharged_kwh: number
  total_grid_import_kwh: number
  total_grid_export_kwh: number
  total_load_kwh: number
  total_pv_kwh: number
  min_soc_reserve_pct: number
  inverter_efficiency: number
  dod_pct: number
  led_on: boolean | null
  ble_broadcast: boolean | null
  power_version_w: number
  device_model: string
  firmware: number | null
  wifi_ssid: string
  wifi_rssi: number | null
  ble_state: string
  charge_allowed: boolean | null
  discharge_allowed: boolean | null
  rated_capacity_wh: number
  ct_connected: boolean | null
  ct_power_w: number
  ct_a_w: number
  ct_b_w: number
  ct_c_w: number
  history: TelemetryPoint[]
  events: StationEvent[]
  sessions: ReserveSession[]
  updated_at: number
}

export const POWER_PRESETS = [400, 800, 1500, 2200, 2500] as const
export const POWER_VERSIONS = [800, 1200, 1500, 2200, 2500] as const
export const MODES: OperatingMode[] = ['Auto', 'AI', 'Manual', 'Passive', 'Ups']
export const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'] as const

export const INITIAL_STATE: StationState = {
  connected: false,
  demo_mode: true,
  latency_ms: null,
  station_name: 'Marstek Venus E',
  station_ip: '192.168.1.100',
  station_port: 30000,
  soc_pct: 0,
  remaining_wh: 0,
  remaining_kwh: 0,
  capacity_kwh: 5.12,
  battery_temp_c: 0,
  battery_voltage_v: 0,
  battery_power_w: 0,
  battery_power_avg_w: 0,
  grid_power_w: 0,
  solar_power_w: 0,
  home_load_w: 0,
  station_self_w: 43,
  station_self_source: 'estimate',
  self_draw: null,
  state: 'idle',
  state_label: 'Підключення…',
  time_remaining_seconds: null,
  time_remaining_label: '—',
  time_remaining_subtitle: 'Очікування',
  mode: 'Auto',
  power_limit_w: 1500,
  passive_countdown_s: 300,
  passive_direction: 'discharge',
  schedules: [],
  daily_charged_kwh: 0,
  daily_discharged_kwh: 0,
  total_grid_import_kwh: 0,
  total_grid_export_kwh: 0,
  total_load_kwh: 0,
  total_pv_kwh: 0,
  min_soc_reserve_pct: 12,
  inverter_efficiency: 0.95,
  dod_pct: 88,
  led_on: null,
  ble_broadcast: null,
  power_version_w: 2500,
  device_model: 'Venus E',
  firmware: null,
  wifi_ssid: '',
  wifi_rssi: null,
  ble_state: '',
  charge_allowed: null,
  discharge_allowed: null,
  rated_capacity_wh: 5120,
  ct_connected: null,
  ct_power_w: 0,
  ct_a_w: 0,
  ct_b_w: 0,
  ct_c_w: 0,
  history: [],
  events: [],
  sessions: [],
  updated_at: 0,
}
