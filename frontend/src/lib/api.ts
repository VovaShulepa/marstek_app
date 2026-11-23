import type {
  DiscoveredDevice,
  ManualSlot,
  OperatingMode,
  PassiveDirection,
  ReserveSession,
  SelfDrawInfo,
  StationState,
} from '../types'

function apiBase(): string {
  return import.meta.env.VITE_API_URL ?? ''
}

export function wsUrl(): string {
  const env = import.meta.env.VITE_WS_URL as string | undefined
  if (env) return env
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws`
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export interface CommandResult {
  ok: boolean
  message: string
  state: StationState | null
}

export async function fetchState(): Promise<StationState> {
  return jsonFetch<StationState>('/api/state')
}

export async function setMode(
  mode: OperatingMode,
  power_limit_w?: number,
  extra?: { passive_countdown_s?: number; passive_direction?: PassiveDirection },
) {
  return jsonFetch<CommandResult>('/api/mode', {
    method: 'POST',
    body: JSON.stringify({ mode, power_limit_w, ...extra }),
  })
}

export async function updateSchedule(slot: ManualSlot) {
  return jsonFetch<CommandResult>('/api/schedule', {
    method: 'POST',
    body: JSON.stringify(slot),
  })
}

export async function updateDevice(body: {
  dod_pct?: number
  led_on?: boolean
  ble_broadcast?: boolean
  power_version_w?: number
}) {
  return jsonFetch<CommandResult>('/api/device', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function discoverDevices() {
  return jsonFetch<{ ok: boolean; message: string; devices: DiscoveredDevice[] }>('/api/discover')
}

export async function updateConfig(body: {
  marstek_ip?: string
  marstek_port?: number
  min_soc_reserve_pct?: number
  inverter_efficiency?: number
  demo_mode?: boolean
}) {
  return jsonFetch<CommandResult>('/api/config', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function clearEvents() {
  return jsonFetch<CommandResult>('/api/events/clear', { method: 'POST', body: '{}' })
}

export async function fetchSessions(): Promise<ReserveSession[]> {
  return jsonFetch<ReserveSession[]>('/api/sessions')
}

export async function fetchSelfDraw(): Promise<SelfDrawInfo> {
  return jsonFetch<SelfDrawInfo>('/api/self-draw')
}

export async function fetchTelemetry(hours = 24) {
  return jsonFetch<{ hours: number; count: number; samples: Array<Record<string, number | string>> }>(
    `/api/telemetry?hours=${hours}`,
  )
}

export async function clearSessions() {
  return jsonFetch<CommandResult>('/api/sessions/clear', { method: 'POST', body: '{}' })
}

export async function updateSimulator(body: {
  home_load_w?: number
  grid_input_w?: number
  soc_pct?: number
  battery_power_w?: number
  temp_c?: number
}) {
  return jsonFetch<CommandResult>('/api/simulator', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function haptic(ms = 15) {
  try {
    navigator.vibrate?.(ms)
  } catch {
    /* ignore */
  }
}
