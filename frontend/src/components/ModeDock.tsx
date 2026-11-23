import { AnimatePresence, motion } from 'framer-motion'
import { ChevronRight, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { haptic, setMode } from '../lib/api'
import { MODES, POWER_PRESETS, type OperatingMode, type PassiveDirection, type StationState } from '../types'

interface Props {
  state: StationState
  onState: (s: StationState) => void
}

const MODE_UA: Record<OperatingMode, string> = {
  Auto: 'Самоспоживання',
  AI: 'AI',
  Manual: 'Ручний',
  Passive: 'Пасивний',
  Ups: 'UPS',
}

export function ModeDock({ state, onState }: Props) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [minutes, setMinutes] = useState(Math.max(1, Math.round((state.passive_countdown_s || 300) / 60)))
  const cap = state.power_version_w || 2500

  const send = async (
    mode: OperatingMode,
    power = state.power_limit_w,
    direction: PassiveDirection = state.passive_direction,
  ) => {
    try {
      const res = await setMode(mode, Math.min(power, cap), {
        passive_countdown_s: Math.max(1, minutes) * 60,
        passive_direction: direction,
      })
      if (res.state) onState(res.state)
      setNote(res.ok ? '' : res.message)
      return res.ok
    } catch {
      setNote('Немає зв’язку з мостом')
      return false
    }
  }

  const applyMode = async (mode: OperatingMode) => {
    haptic(15)
    const ok = await send(mode)
    if (ok && mode !== 'Passive') setOpen(false)
  }

  const applyPower = async (power_limit_w: number) => {
    haptic(12)
    await send(state.mode, power_limit_w)
  }

  const applyDirection = async (direction: PassiveDirection) => {
    haptic(12)
    await send(state.mode === 'Passive' ? 'Passive' : state.mode, state.power_limit_w, direction)
  }

  return (
    <div className="fixed inset-x-0 bottom-0 z-30 px-6 pb-[max(0.7rem,env(safe-area-inset-bottom))]">
      <div className="mx-auto max-w-lg">
        <AnimatePresence>
          {open && (
            <motion.div
              className="glass mb-2 max-h-[58dvh] space-y-3 overflow-y-auto p-3"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="grid grid-cols-2 gap-2">
                {MODES.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => applyMode(mode)}
                    className={`rounded-xl px-2 py-2.5 text-[13px] font-medium ${
                      state.mode === mode
                        ? 'bg-[#22d068]/15 text-[#b6f5d0] ring-1 ring-[#22d068]/35'
                        : 'bg-white/5 text-slate-300'
                    }`}
                  >
                    {MODE_UA[mode]}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap gap-1.5">
                {POWER_PRESETS.filter((w) => w <= cap).map((w) => (
                  <button
                    key={w}
                    type="button"
                    onClick={() => applyPower(w)}
                    className={`rounded-full px-2.5 py-1 text-[11px] ${
                      state.power_limit_w === w ? 'bg-white/15 text-white' : 'bg-white/5 text-slate-400'
                    }`}
                  >
                    {w} Вт
                  </button>
                ))}
              </div>
              <input
                type="range"
                min={100}
                max={cap}
                step={50}
                value={Math.min(state.power_limit_w, cap)}
                onChange={(e) => onState({ ...state, power_limit_w: Number(e.target.value) })}
                onMouseUp={(e) => applyPower(Number((e.target as HTMLInputElement).value))}
                onTouchEnd={(e) => applyPower(Number((e.target as HTMLInputElement).value))}
                className="w-full"
                aria-label="Потужність пасивного режиму і розкладу"
              />
              <p className="text-[11px] leading-snug text-white/35">
                Повзунок задає вати для пасивного режиму. Авто, AI і UPS керують станцією самі. Ліміт
                інвертора зараз {cap} Вт.
              </p>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => applyDirection('charge')}
                  className={`flex-1 rounded-xl px-2 py-2 text-[12px] ${
                    state.passive_direction === 'charge' ? 'bg-white/15 text-white' : 'bg-white/5 text-slate-400'
                  }`}
                >
                  Заряд
                </button>
                <button
                  type="button"
                  onClick={() => applyDirection('discharge')}
                  className={`flex-1 rounded-xl px-2 py-2 text-[12px] ${
                    state.passive_direction === 'discharge' ? 'bg-white/15 text-white' : 'bg-white/5 text-slate-400'
                  }`}
                >
                  Розряд
                </button>
                <label className="flex items-center gap-1 rounded-xl bg-white/5 px-2 py-2 text-[12px] text-slate-300">
                  <input
                    value={minutes}
                    onChange={(e) => setMinutes(Number(e.target.value) || 1)}
                    onBlur={() => {
                      if (state.mode === 'Passive') applyPower(state.power_limit_w)
                    }}
                    inputMode="numeric"
                    className="w-10 bg-transparent text-center text-white outline-none"
                    aria-label="Хвилини пасивного режиму"
                  />
                  хв
                </label>
              </div>

              {note && <p className="text-center text-[12px] text-[#e8a04a]">{note}</p>}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="glass flex items-center gap-2 rounded-2xl px-2 py-2">
          <button
            type="button"
            onClick={() => {
              haptic(10)
              document.getElementById('station-facts')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }}
            className={`flex h-11 w-[52px] items-center justify-center rounded-xl text-sm font-semibold ring-1 ${
              state.ct_connected
                ? 'bg-[#22d068]/12 text-[#22d068] ring-[#22d068]/40'
                : 'bg-white/5 text-slate-400 ring-white/10'
            }`}
          >
            CT
          </button>
          <button
            type="button"
            onClick={() => {
              haptic(10)
              setOpen((v) => !v)
            }}
            className="flex h-11 flex-1 items-center justify-between px-2 text-left"
          >
            <span className="text-[13px] text-slate-400">Режими</span>
            <span className="flex items-center gap-1 text-[15px] font-medium text-white">
              {MODE_UA[state.mode] ?? state.mode}
              {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
            </span>
          </button>
        </div>
      </div>
    </div>
  )
}
