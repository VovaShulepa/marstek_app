import { ChevronRight } from 'lucide-react'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { duration, groupSessions, kwh, pct, power, sessionsWord } from '../lib/reserve'
import type { ReserveSession, StationState } from '../types'

interface Props {
  state: StationState
  onOpenHistory: () => void
}

export function ReserveJournal({ state, onOpenHistory }: Props) {
  const sessions = state.sessions ?? []
  const live = sessions.find((session) => session.ended_at == null) ?? null
  const now = useNow(live != null)
  const days = groupSessions(sessions, now)
  const today = days.find((day) => day.label === 'Сьогодні')
  const yesterday = days.find((day) => day.label === 'Вчора')

  return (
    <motion.section
      id="reserve-journal"
      className="glass relative z-[1] scroll-mb-32 px-4 py-4"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
    >
      <div>
        <h2 className="text-[13px] font-medium text-white/55">Облік резерву</h2>
        <p className="mt-1 text-[11px] text-white/35">Сесії роботи станції від запасу</p>
      </div>

      {live ? (
        <LiveSession session={live} now={now} state={state} />
      ) : (
        sessions.length === 0 && (
          <p className="mt-3 text-[13px] leading-relaxed text-white/50">
            Сесія почнеться, коли станція віддає запас у дім. Тут лишиться старт у відсотках і кВт·год, скільки вже
            пішло, темп споживання і на скільки годин вистачить.
          </p>
        )
      )}

      <button
        type="button"
        onClick={onOpenHistory}
        className="mt-3 flex w-full items-center justify-between gap-3 rounded-xl bg-black/20 px-3 py-2.5 text-left"
      >
        <span className="min-w-0">
          <span className="block text-[13px] font-medium text-white">Історія</span>
          <span className="mt-0.5 block text-[12px] leading-snug text-white/45">
            {today || yesterday ? (
              <>
                {today && <DayLine day={today} />}
                {yesterday && (
                  <>
                    {today ? <br /> : null}
                    <DayLine day={yesterday} />
                  </>
                )}
              </>
            ) : (
              'Сесії по днях: скільки тривали і скільки забрали'
            )}
          </span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-white/40" />
      </button>
    </motion.section>
  )
}

function DayLine({ day }: { day: { label: string; items: ReserveSession[]; seconds: number; usedWh: number } }) {
  return (
    <>
      {day.label} {day.items.length} {sessionsWord(day.items.length)} · {duration(day.seconds)} · {kwh(day.usedWh)}
    </>
  )
}

function LiveSession({
  session,
  now,
  state,
}: {
  session: ReserveSession
  now: number
  state: StationState
}) {
  const elapsed = Math.max(0, now / 1000 - session.started_at)
  // Same live clock as the main battery card — not the session-average forecast.
  const remaining = state.time_remaining_seconds
  const enough = remaining != null && remaining > 0
  const avgReady = session.avg_w >= 25

  return (
    <div className="mt-3 rounded-2xl bg-black/25 px-3.5 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-[12px] font-medium text-[#f6a323]">
            <i className="status-dot is-discharge is-live" />
            Зараз на резерві
          </p>
          <p className="mt-1.5 text-[28px] font-semibold leading-none tracking-[-0.04em] text-white tabular-nums">
            {duration(elapsed)}
          </p>
        </div>
        <p className="pt-0.5 text-right text-[12px] tabular-nums text-white/45">старт {clock(session.started_at)}</p>
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-2">
        <Metric label="Запас на старті" value={pct(session.start_soc_pct)} hint={kwh(session.start_wh)} />
        <Metric label="Взяло" value={pct(session.used_pct)} hint={kwh(session.used_wh)} tone="#f6a323" />
        <Metric label="Споживання" value={avgReady ? power(session.avg_w) : 'рахую'} hint="середнє за сесію" />
        <Metric
          label="Вистачить"
          value={
            remaining == null
              ? 'рахую'
              : remaining <= 0
                ? 'на межі'
                : state.time_remaining_label
          }
          hint={enough ? 'до вимкнення' : 'за цим темпом'}
          tone={enough ? '#8cf0b4' : undefined}
        />
      </div>

      <SocSpan start={session.start_soc_pct} end={session.end_soc_pct} />
    </div>
  )
}

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint: string
  tone?: string
}) {
  return (
    <div className="rounded-xl bg-white/[0.04] px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-wider text-white/35">{label}</p>
      <p
        className="mt-1 text-[16px] font-semibold leading-none tracking-[-0.03em] tabular-nums"
        style={{ color: tone ?? '#fff' }}
      >
        {value}
      </p>
      <p className="mt-1.5 text-[11px] text-white/40">{hint}</p>
    </div>
  )
}

function SocSpan({ start, end }: { start: number; end: number }) {
  const from = Math.max(0, Math.min(100, start))
  const to = Math.max(0, Math.min(100, end))
  const left = Math.min(from, to)
  const width = Math.max(0, Math.abs(from - to))
  return (
    <div className="mt-3.5">
      <div className="relative h-1.5 overflow-hidden rounded-full bg-white/10">
        <span className="absolute inset-y-0 left-0 rounded-full bg-white/30" style={{ width: `${to}%` }} />
        {width > 0.2 && (
          <span className="absolute inset-y-0 rounded-full bg-[#f6a323]" style={{ left: `${left}%`, width: `${width}%` }} />
        )}
      </div>
      <p className="mt-1.5 flex justify-between text-[11px] tabular-nums text-white/40">
        <span>старт {pct(start)}</span>
        <span>зараз {pct(end)}</span>
      </p>
    </div>
  )
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

function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}
