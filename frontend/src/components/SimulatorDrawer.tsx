import { SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { updateSimulator } from '../lib/api'
import type { StationState } from '../types'

interface Props {
  state: StationState
  onState: (s: StationState) => void
}

export function SimulatorDrawer({ state, onState }: Props) {
  const [open, setOpen] = useState(false)
  const [load, setLoad] = useState(state.home_load_w)
  const [grid, setGrid] = useState(state.grid_power_w)
  const [soc, setSoc] = useState(state.soc_pct)
  const [bat, setBat] = useState(state.battery_power_w)

  if (!state.demo_mode) return null

  const push = async (patch: {
    home_load_w?: number
    grid_input_w?: number
    soc_pct?: number
    battery_power_w?: number
  }) => {
    try {
      const res = await updateSimulator(patch)
      if (res.state) onState(res.state)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="fixed bottom-[5.15rem] right-3 z-40 flex w-[min(20rem,calc(100%-1.5rem))] flex-col items-end">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-full border border-white/10 bg-black/50 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 shadow-lg backdrop-blur-md"
        aria-label="Симулятор DEMO"
      >
        <SlidersHorizontal className="h-3.5 w-3.5" />
        {open ? 'Закрити' : 'DEMO'}
      </button>

      {open && (
        <div className="glass mt-2 space-y-4 p-4 shadow-2xl">
          <Slider
            label="Навантаження дому"
            unit="Вт"
            min={0}
            max={4000}
            value={load}
            onChange={setLoad}
            onCommit={(v) => push({ home_load_w: v })}
          />
          <Slider
            label="Мережа / вхід"
            unit="Вт"
            min={0}
            max={4000}
            value={grid}
            onChange={setGrid}
            onCommit={(v) => push({ grid_input_w: v })}
          />
          <Slider
            label="SOC"
            unit="%"
            min={0}
            max={100}
            value={soc}
            onChange={setSoc}
            onCommit={(v) => push({ soc_pct: v })}
          />
          <Slider
            label="Потужність АКБ (+ заряд / − розряд)"
            unit="Вт"
            min={-2500}
            max={2500}
            value={bat}
            onChange={setBat}
            onCommit={(v) => push({ battery_power_w: v })}
          />
        </div>
      )}
    </div>
  )
}

function Slider({
  label,
  unit,
  min,
  max,
  value,
  onChange,
  onCommit,
}: {
  label: string
  unit: string
  min: number
  max: number
  value: number
  onChange: (v: number) => void
  onCommit: (v: number) => void
}) {
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="mono text-slate-200">
          {Math.round(value)} {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={10}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        onMouseUp={(e) => onCommit(Number((e.target as HTMLInputElement).value))}
        onTouchEnd={(e) => onCommit(Number((e.target as HTMLInputElement).value))}
        className="w-full"
      />
    </div>
  )
}
