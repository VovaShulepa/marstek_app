import { motion } from 'framer-motion'
import { useAnimatedNumber } from '../hooks/useAnimatedNumber'
import type { StationState } from '../types'

interface Props {
  state: StationState
}

export function BatteryCard({ state }: Props) {
  const kwh = useAnimatedNumber(state.remaining_kwh, 2)
  const socAnim = useAnimatedNumber(state.soc_pct, 0)
  const soc = Math.max(0, Math.min(100, state.soc_pct))
  const charging = state.state === 'charging'
  const discharging = state.state === 'discharging'
  const status = charging ? 'Заряд' : discharging ? 'Резерв' : 'Увімкнена'
  const time = state.time_remaining_label
  const hasTime = Boolean(time && time !== '—' && time !== '-')
  const hint = charging ? 'До повного заряду' : 'Залишилось'

  return (
    <motion.section
      className="liquid"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="relative z-[1] flex items-center gap-3 px-3.5 py-3">
        <div className="relative h-16 w-11 shrink-0">
          <span className="pointer-events-none absolute bottom-0.5 left-1/2 h-2 w-[76%] -translate-x-1/2 rounded-full bg-black/70 blur-md" />
          <img
            src="/venus-station.png?v=2"
            alt="Marstek Venus E 3.0"
            className="relative z-[1] h-full w-full object-contain"
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="status-chip" data-mode={charging ? 'charge' : discharging ? 'discharge' : 'idle'}>
                <span className={`status-dot ${discharging ? 'is-discharge is-live' : ''} ${charging ? 'is-live' : ''}`} />
                {status}
              </p>
              <p className="mt-2 text-[15px] font-semibold leading-none tracking-[-0.02em] text-white tabular-nums">
                {kwh.toFixed(2)}
                <span className="ml-1 text-[11px] font-medium text-white/40">kWh</span>
              </p>
            </div>
            <p className="flex shrink-0 items-center text-white tabular-nums">
              <span className="text-[34px] font-semibold leading-none tracking-[-0.045em]">
                {Math.round(socAnim)}
              </span>
              <span className="ml-0.5 text-[15px] font-medium leading-none text-white/40">%</span>
            </p>
          </div>

          <div className="relative mt-2.5 h-2.5 overflow-hidden rounded-full bg-white/10">
            <motion.div
              className="relative h-full overflow-hidden rounded-full"
              style={{
                background: 'linear-gradient(90deg, #f25c45 0%, #f6a323 32%, #22d068 78%, #3ecfbf 100%)',
              }}
              initial={false}
              animate={{ width: `${Math.max(soc > 0 ? 8 : 0, soc)}%` }}
              transition={{ type: 'spring', stiffness: 42, damping: 18 }}
            >
              {discharging && <span className="scale-arrows to-zero" />}
              {charging && <span className="scale-arrows to-full" />}
            </motion.div>
          </div>

          <p className="mt-2 flex items-baseline justify-between gap-3 whitespace-nowrap leading-none">
            <span
              className="text-[12px] font-medium"
              style={{ color: hasTime ? (discharging ? '#f6a323' : '#8cf0b4') : 'rgba(255,255,255,0.45)' }}
            >
              {hasTime ? hint : 'Без навантаження'}
            </span>
            {hasTime && (
              <span className="text-[14px] font-semibold tracking-[-0.02em] text-white tabular-nums">{time}</span>
            )}
          </p>
        </div>
      </div>
    </motion.section>
  )
}
