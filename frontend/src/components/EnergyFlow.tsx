import { motion } from 'framer-motion'
import { useAnimatedNumber } from '../hooks/useAnimatedNumber'
import type { StationState } from '../types'

interface Props {
  state: StationState
}

export function EnergyFlow({ state }: Props) {
  const grid = useAnimatedNumber(Math.abs(state.grid_power_w), 0)
  const load = useAnimatedNumber(state.home_load_w, 0)
  const self = useAnimatedNumber(state.station_self_w ?? 43, 0)
  const selfHint = state.station_self_source === 'measured' ? 'з логів' : 'оцінка'
  const gridHint = state.grid_power_w > 30 ? 'імпорт' : state.grid_power_w < -30 ? 'експорт' : 'тихо'
  const houseOn = load > 30

  return (
    <motion.section
      className="relative"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="relative z-[1] grid grid-cols-3 items-end gap-3 px-1 text-center">
        <Column
          label="Станція"
          watts={self}
          hint={selfHint}
          color="#f6a323"
          delay="0s"
          live={state.station_self_source === 'measured'}
          signed
        />
        <Column
          label="Дім"
          watts={load}
          hint={houseOn ? 'споживання' : 'тихо'}
          color={houseOn ? '#f6a323' : '#f4f7fb'}
          delay="0.12s"
          live={houseOn}
          emphasize
          signed={houseOn}
        />
        <Column label="Мережа" watts={grid} hint={gridHint} color="#f4f7fb" delay="0.24s" live={Math.abs(state.grid_power_w) > 30} />
      </div>
      <img
        src="/house-scene.jpg"
        alt=""
        className="pointer-events-none relative z-0 -mt-6 mb-2 h-[280px] w-full object-cover object-[center_62%]"
        style={{
          WebkitMaskImage:
            'linear-gradient(to bottom, transparent 0%, #000 12%, #000 94%, transparent 100%)',
          maskImage:
            'linear-gradient(to bottom, transparent 0%, #000 12%, #000 94%, transparent 100%)',
        }}
      />
    </motion.section>
  )
}

function Column({
  label,
  watts,
  hint,
  color,
  delay,
  live,
  emphasize = false,
  signed = false,
}: {
  label: string
  watts: number
  hint?: string
  color: string
  delay: string
  live: boolean
  emphasize?: boolean
  signed?: boolean
}) {
  return (
    <div className="flex flex-col items-center">
      <p
        className={`font-medium tracking-[0.04em] ${emphasize ? 'text-[13px]' : 'text-[12px]'} ${emphasize || signed ? '' : 'text-white/50'}`}
        style={emphasize || signed ? { color } : undefined}
      >
        {label}
      </p>
      <p
        className={`mt-2 flex h-9 items-end whitespace-nowrap font-semibold leading-none tracking-[-0.03em] tabular-nums ${emphasize ? 'text-[30px]' : 'text-[22px]'}`}
        style={{ color }}
      >
        {signed ? '−' : ''}
        {Math.round(watts)}
        <span
          className={`mb-0.5 ml-1 font-medium tracking-normal ${emphasize ? 'text-[13px]' : 'text-[11px]'} ${emphasize || signed ? '' : 'text-white/40'}`}
          style={emphasize || signed ? { color } : undefined}
        >
          Вт
        </span>
      </p>
      <p
        className="mt-1.5 h-3.5 text-[10px] leading-none"
        style={{ color: emphasize || signed ? color : 'rgba(255,255,255,0.35)' }}
      >
        {hint ?? ''}
      </p>
      <div
        className={`flow-dash mt-2 ${emphasize ? 'h-20' : 'h-16'}`}
        style={{ ['--flow' as string]: color, animationPlayState: live ? 'running' : 'paused', animationDelay: delay }}
      />
    </div>
  )
}
