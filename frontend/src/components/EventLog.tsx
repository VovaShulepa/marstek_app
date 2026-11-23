import { motion } from 'framer-motion'
import { clearEvents } from '../lib/api'
import type { StationEvent, StationState } from '../types'

interface Props {
  state: StationState
  onState: (state: StationState) => void
}

export function openEvents(state: StationState): StationEvent[] {
  return (state.events ?? []).filter((event) => event.ended_at == null)
}

export function ActiveAlert({ state }: { state: StationState }) {
  const active = openEvents(state)
  if (!active.length) return null
  const first = active[0]
  const tone = first.level === 'error' ? '#ff5d5d' : '#f6a323'
  return (
    <button
      type="button"
      onClick={() => document.getElementById('event-log')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
      className="glass flex w-full items-center gap-3 px-4 py-3 text-left"
    >
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: tone, boxShadow: `0 0 8px ${tone}` }} />
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] font-semibold" style={{ color: tone }}>
          {first.title}
          {active.length > 1 ? ` · ще ${active.length - 1}` : ''}
        </span>
        <span className="mt-0.5 block truncate text-[12px] text-white/55">{first.detail}</span>
      </span>
    </button>
  )
}

export function EventLog({ state, onState }: Props) {
  const events = state.events ?? []

  const wipe = async () => {
    try {
      const result = await clearEvents()
      if (result.state) onState(result.state)
    } catch {
      /* журнал лишається, доки запит не пройде */
    }
  }

  return (
    <motion.section
      id="event-log"
      className="glass relative z-[1] scroll-mb-32 px-4 py-4"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-[13px] font-medium text-white/55">Журнал</h2>
          <p className="mt-1 text-[11px] text-white/35">Помічає стан само і тримає історію</p>
        </div>
        {events.length > 0 && (
          <button type="button" onClick={() => void wipe()} className="text-[12px] text-white/45 hover:text-white">
            Очистити
          </button>
        )}
      </div>

      {events.length === 0 ? (
        <p className="mt-3 text-[13px] leading-relaxed text-white/50">
          Поки тихо. Сюди потраплять завелике споживання, заряд біля резерву, перегрів, слабкий Wi‑Fi і обрив
          зв’язку.
        </p>
      ) : (
        <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
          {events.map((event) => (
            <EventRow key={event.id} event={event} />
          ))}
        </ul>
      )}
    </motion.section>
  )
}

function EventRow({ event }: { event: StationEvent }) {
  const open = event.ended_at == null
  const tone = event.level === 'error' ? '#ff5d5d' : event.level === 'warning' ? '#f6a323' : '#9aa6b5'
  const span =
    event.ended_at && event.ended_at - event.ts >= 30 ? ` · ${duration(event.ts, event.ended_at)}` : ''
  return (
    <li className="rounded-xl bg-black/20 px-3 py-2.5" style={{ opacity: open ? 1 : 0.72 }}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="flex min-w-0 items-center gap-2 text-[13px] font-semibold" style={{ color: tone }}>
          <i className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: tone }} />
          <span className="truncate">{event.title}</span>
        </p>
        <p className="shrink-0 text-[11px] tabular-nums text-white/40">
          {open ? 'зараз' : stamp(event.ts)}
          {span}
        </p>
      </div>
      {event.detail && <p className="mt-1 pl-3.5 text-[12px] leading-snug text-white/55">{event.detail}</p>}
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

function duration(start: number, end: number): string {
  const mins = Math.max(1, Math.round((end - start) / 60))
  if (mins < 60) return `${mins} хв`
  const hours = Math.floor(mins / 60)
  const rest = mins % 60
  return rest ? `${hours} год ${rest} хв` : `${hours} год`
}
