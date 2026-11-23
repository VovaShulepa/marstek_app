import { ChevronDown, ChevronLeft } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { clearSessions, fetchSessions } from '../lib/api'
import { clock, duration, groupSessions, kwh, pct, power, sessionsWord, sessionSeconds } from '../lib/reserve'
import type { ReserveSession, StationState } from '../types'

interface Props {
  state: StationState
  onClose: () => void
  onState: (state: StationState) => void
}

export function ReserveHistory({ state, onClose, onState }: Props) {
  const [stored, setStored] = useState<ReserveSession[]>(state.sessions ?? [])
  const [openDays, setOpenDays] = useState<Set<string> | null>(null)
  const live = (state.sessions ?? []).some((session) => session.ended_at == null)
  const now = useNow(live)

  useEffect(() => {
    let cancel = false
    fetchSessions()
      .then((rows) => {
        if (!cancel) setStored(rows)
      })
      .catch(() => {
        /* на екрані лишається те, що вже прийшло з ефіру */
      })
    return () => {
      cancel = true
    }
  }, [])

  useEffect(() => {
    const incoming = state.sessions ?? []
    if (!incoming.length) return
    setStored((prev) => {
      const byId = new Map(prev.map((session) => [session.id, session]))
      for (const session of incoming) byId.set(session.id, session)
      return [...byId.values()]
    })
  }, [state.sessions])

  const days = useMemo(() => groupSessions(stored, now), [stored, now])
  const todayKey = days.find((day) => day.label === 'Сьогодні')?.key

  const wipe = async () => {
    try {
      const result = await clearSessions()
      if (result.state) {
        onState(result.state)
        setStored([])
      }
    } catch {
      /* журнал лишається, доки запит не пройде */
    }
  }

  return (
    <div className="app-shell fixed inset-0 z-40 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-lg flex-col gap-4 px-5 pb-12 pt-[max(1rem,env(safe-area-inset-top))]">
        <header className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-1 text-[14px] font-medium text-white/70 hover:text-white"
          >
            <ChevronLeft className="h-5 w-5" />
            Назад
          </button>
          {stored.length > 0 && (
            <button type="button" onClick={() => void wipe()} className="text-[12px] text-white/45 hover:text-white">
              Очистити
            </button>
          )}
        </header>

        <div>
          <h1 className="text-[22px] font-semibold tracking-[-0.03em] text-white">Історія резерву</h1>
          <p className="mt-1 text-[13px] leading-relaxed text-white/45">
            Сесії пишуться локально. По дню видно, скільки разів станція працювала, як довго і скільки запасу
            забрала.
          </p>
        </div>

        {days.length === 0 ? (
          <p className="glass px-4 py-4 text-[13px] leading-relaxed text-white/55">
            Поки порожньо. Перша сесія з’явиться, коли станція віддасть запас у дім.
          </p>
        ) : (
          days.map((day) => {
            const expanded = openDays === null ? day.label === 'Сьогодні' : openDays.has(day.key)
            return (
              <section key={day.key} className="glass px-3.5 py-3">
                <button
                  type="button"
                  onClick={() =>
                    setOpenDays((prev) => {
                      const next = new Set(prev ?? (todayKey ? [todayKey] : []))
                      if (next.has(day.key)) next.delete(day.key)
                      else next.add(day.key)
                      return next
                    })
                  }
                  className="flex w-full items-start justify-between gap-3 text-left"
                >
                  <span>
                    <span className="block text-[15px] font-semibold text-white">{day.label}</span>
                    <span className="mt-1 block text-[12px] leading-snug text-white/50">
                      {day.items.length} {sessionsWord(day.items.length)} · {duration(day.seconds)} · {kwh(day.usedWh)}
                    </span>
                  </span>
                  <ChevronDown
                    className={`mt-0.5 h-4 w-4 shrink-0 text-white/40 transition-transform ${expanded ? 'rotate-180' : ''}`}
                  />
                </button>
                {expanded && (
                  <ul className="mt-3 space-y-2">
                    {day.items.map((session) => (
                      <SessionRow key={session.id} session={session} now={now} />
                    ))}
                  </ul>
                )}
              </section>
            )
          })
        )}
      </div>
    </div>
  )
}

function SessionRow({ session, now }: { session: ReserveSession; now: number }) {
  const end = session.ended_at ?? now / 1000
  const open = session.ended_at == null
  return (
    <li className="rounded-xl bg-black/25 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[14px] font-semibold tabular-nums text-white">{duration(sessionSeconds(session, now))}</p>
        <p className="shrink-0 text-[11px] tabular-nums text-white/40">
          {open ? 'зараз' : `${clock(session.started_at)}–${clock(end)}`}
        </p>
      </div>
      <p className="mt-1 text-[12px] leading-snug text-white/70">
        Взяло {pct(session.used_pct)} і {kwh(session.used_wh)}
        {session.avg_w >= 25 ? ` · ${power(session.avg_w)}` : ''}
      </p>
      <p className="mt-0.5 text-[11px] text-white/40">
        Старт {pct(session.start_soc_pct)} · {kwh(session.start_wh)}
        {open ? '' : ` → ${pct(session.end_soc_pct)} · ${kwh(session.end_wh)}`}
      </p>
    </li>
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
