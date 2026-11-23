import { motion } from 'framer-motion'
import { useAnimatedNumber } from '../hooks/useAnimatedNumber'
import type { StationState } from '../types'

interface Props {
  state: StationState
}

export function StatsCards({ state }: Props) {
  const charged = useAnimatedNumber(state.daily_charged_kwh, 2)
  const discharged = useAnimatedNumber(state.daily_discharged_kwh, 2)
  const imported = useAnimatedNumber(state.total_grid_import_kwh, 1)
  const exported = useAnimatedNumber(state.total_grid_export_kwh, 1)

  return (
    <motion.section
      className="glass relative z-[1] px-4 py-4"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="grid grid-cols-2 gap-x-4 gap-y-4">
        <Stat label="Заряд сьогодні" value={charged.toFixed(2)} hint="у батарею" />
        <Stat label="Розряд сьогодні" value={discharged.toFixed(2)} hint="у дім" />
        <Stat label="Імпорт з мережі" value={imported.toFixed(1)} hint="за весь час" />
        <Stat label="Експорт у мережу" value={exported.toFixed(1)} hint="за весь час" />
      </div>
    </motion.section>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <p className="text-[12px] font-medium text-white/45">{label}</p>
      <p className="mt-1.5 text-[22px] font-semibold leading-none tracking-[-0.03em] text-white tabular-nums">
        {value}
        <span className="ml-1 text-[12px] font-medium text-white/35">kWh</span>
      </p>
      <p className="mt-1.5 text-[11px] text-white/35">{hint}</p>
    </div>
  )
}
