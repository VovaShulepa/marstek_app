import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { duration, kwh, pct, power } from '../lib/reserve'
import type { DrainWindow, IdleStretch, StationState } from '../types'

interface Props {
  state: StationState
}

export function SelfDrawCard({ state }: Props) {
  const info = state.self_draw
  const watts = Math.round(state.station_self_w ?? info?.watts ?? 43)
  const measured = (state.station_self_source ?? info?.source) === 'measured'
  const open = info?.idle_open ?? null
  const windows = info?.windows ?? []
  const past = (info?.idle ?? []).filter((row) => row.ended_at != null).slice(0, 4)
  const now = useNow(open != null)

  return (
    <motion.section
      className="glass relative z-[1] scroll-mb-28 px-4 py-4"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.13, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[13px] font-medium text-white/55">Власне споживання</h2>
          <p className="mt-1 text-[11px] leading-snug text-white/35">
            Лог пише SOC і вати кожні 30 с. Коли станція просто увімкнена без резерву — міряємо, скільки вона сама
            з’їла.
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[22px] font-semibold leading-none tracking-[-0.03em] tabular-nums text-white">
            {watts}
            <span className="ml-1 text-[12px] font-medium text-white/40">Вт</span>
          </p>
          <p className="mt-1 text-[11px]" style={{ color: measured ? '#8cf0b4' : 'rgba(255,255,255,0.4)' }}>
            {measured ? 'з логів' : 'оцінка 10%/12 год'}
          </p>
        </div>
      </div>

      {open ? (
        <OpenIdle stretch={open} now={now} />
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-white/45">
          Залиш станцію увімкненою без розряду в дім на годину або довше. Тоді з падіння заряду порахуємо реальні
          вати і підставимо їх у «Залишилось».
        </p>
      )}

      {windows.some((row) => row.available) && (
        <div className="mt-3.5 grid grid-cols-2 gap-2">
          {windows.map((row) => (
            <Window key={row.hours} row={row} />
          ))}
        </div>
      )}

      {past.length > 0 && (
        <div className="mt-3.5">
          <p className="text-[11px] uppercase tracking-wider text-white/35">Тиша без резерву</p>
          <ul className="mt-2 space-y-2">
            {past.map((stretch) => (
              <PastIdle key={stretch.id} stretch={stretch} />
            ))}
          </ul>
        </div>
      )}
    </motion.section>
  )
}

function OpenIdle({ stretch, now }: { stretch: IdleStretch; now: number }) {
  const elapsed = Math.max(0, now / 1000 - stretch.started_at)
  return (
    <div className="mt-3 rounded-2xl bg-black/25 px-3.5 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[12px] font-medium text-[#f6a323]">Міряю зараз</p>
        <p className="text-[13px] font-semibold tabular-nums text-white">{duration(elapsed)}</p>
      </div>
      <p className="mt-1.5 text-[12px] leading-snug text-white/65">
        З’їла {pct(stretch.used_pct)} і {kwh(stretch.used_wh)}
        {stretch.avg_w >= 5 ? ` · ${power(stretch.avg_w)}` : ''}
        {stretch.pct_per_12h > 0 ? ` · ≈${stretch.pct_per_12h.toFixed(1)}% / 12 год` : ''}
      </p>
      <p className="mt-1 text-[11px] text-white/40">
        Старт {pct(stretch.start_soc_pct)} · зараз {pct(stretch.end_soc_pct)}
      </p>
    </div>
  )
}

function Window({ row }: { row: DrainWindow }) {
  if (!row.available) {
    return (
      <div className="rounded-xl bg-black/20 px-3 py-2.5">
        <p className="text-[10px] uppercase tracking-wider text-white/35">{row.hours} год</p>
        <p className="mt-1 text-[13px] text-white/35">збираю</p>
      </div>
    )
  }
  return (
    <div className="rounded-xl bg-black/20 px-3 py-2.5">
      <p className="flex items-center justify-between gap-2 text-[10px] uppercase tracking-wider text-white/35">
        <span>{row.hours} год</span>
        <span style={{ color: row.quiet ? '#8cf0b4' : 'rgba(255,255,255,0.35)' }}>
          {row.quiet ? 'тихо' : 'з навантаженням'}
        </span>
      </p>
      <p className="mt-1 text-[15px] font-semibold tabular-nums text-white">
        {pct(row.used_pct)}
        <span className="ml-1 text-[11px] font-medium text-white/40">{power(row.avg_w)}</span>
      </p>
      <p className="mt-1 text-[11px] text-white/40">
        {kwh(row.used_wh)}
        {row.pct_per_12h > 0 ? ` · ${row.pct_per_12h.toFixed(1)}%/12г` : ''}
      </p>
    </div>
  )
}

function PastIdle({ stretch }: { stretch: IdleStretch }) {
  const end = stretch.ended_at ?? stretch.updated_at
  return (
    <li className="rounded-xl bg-black/20 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[13px] font-semibold tabular-nums text-white">{duration(end - stretch.started_at)}</p>
        <p className="text-[11px] tabular-nums text-white/40">{stamp(stretch.started_at)}</p>
      </div>
      <p className="mt-1 text-[12px] text-white/65">
        {pct(stretch.used_pct)} · {kwh(stretch.used_wh)} · {power(stretch.avg_w)}
        {stretch.pct_per_12h > 0 ? ` · ${stretch.pct_per_12h.toFixed(1)}%/12г` : ''}
      </p>
    </li>
  )
}

function stamp(ts: number): string {
  const date = new Date(ts * 1000)
  const time = date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
  const now = new Date()
  if (date.toDateString() === now.toDateString()) return time
  const day = `${date.getDate()}`.padStart(2, '0')
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  return `${day}.${month} ${time}`
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    setNow(Date.now())
    const id = window.setInterval(() => setNow(Date.now()), 15000)
    return () => window.clearInterval(id)
  }, [active])
  return now
}
