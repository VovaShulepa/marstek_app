import { motion } from 'framer-motion'
import type { StationState } from '../types'

interface Props {
  state: StationState
}

export function StationFacts({ state }: Props) {
  const temp = Number.isFinite(state.battery_temp_c) ? state.battery_temp_c : 0
  const rssi = state.wifi_rssi
  const ct =
    state.ct_connected == null ? '—' : state.ct_connected ? `${Math.round(state.ct_power_w)} Вт` : 'немає'

  return (
    <motion.section
      id="station-facts"
      className="glass relative z-[1] scroll-mb-28 px-4 py-3.5"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[13px] font-medium text-white/50">Станція</p>
        <p className="truncate text-[13px] text-white/80">
          {state.device_model || 'Venus E'}
          {state.firmware != null ? ` · FW ${state.firmware}` : ''}
        </p>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Fact label="Температура" value={`${temp.toFixed(1)}°`} />
        <Fact label={state.wifi_ssid || 'Wi‑Fi'} value={rssi == null ? '—' : `${rssi} дБм`} />
        <Fact label="CT" value={ct} />
      </div>

      {state.ct_connected && (
        <p className="mt-2.5 text-center text-[12px] tabular-nums text-white/45">
          A {Math.round(state.ct_a_w)} · B {Math.round(state.ct_b_w)} · C {Math.round(state.ct_c_w)} Вт
        </p>
      )}

      <div className="mt-3.5 flex gap-2.5">
        <Flag on={state.charge_allowed} label="Заряд" tone="#22d068" />
        <Flag on={state.discharge_allowed} label="Розряд" tone="#f6a323" />
      </div>
    </motion.section>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/20 px-2 py-2 text-center">
      <p className="truncate text-[10px] uppercase tracking-wider text-white/35">{label}</p>
      <p className="mt-1 truncate text-[14px] font-semibold tabular-nums text-white">{value}</p>
    </div>
  )
}

function Flag({ on, label, tone }: { on: boolean | null; label: string; tone: string }) {
  const text = on == null ? '—' : on ? 'дозволено' : 'стоп'
  return (
    <div className="flex flex-1 items-center justify-between gap-2 rounded-xl bg-black/20 px-3 py-2.5">
      <span className="flex items-center gap-2 text-[13px] font-medium" style={{ color: tone }}>
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: tone, opacity: on === false ? 0.35 : 1 }} />
        {label}
      </span>
      <span className="text-[12px] text-white/50">{text}</span>
    </div>
  )
}
