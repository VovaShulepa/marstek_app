import type { ReserveSession } from '../types'

export interface DayGroup {
  key: string
  label: string
  items: ReserveSession[]
  seconds: number
  usedWh: number
}

export function groupSessions(sessions: ReserveSession[], nowMs: number): DayGroup[] {
  const buckets = new Map<string, ReserveSession[]>()
  for (const session of sessions) {
    const key = dayKey(session.started_at)
    const list = buckets.get(key) ?? []
    list.push(session)
    buckets.set(key, list)
  }
  return [...buckets.values()]
    .map((items) => {
      items.sort((a, b) => b.started_at - a.started_at)
      const seconds = items.reduce((sum, item) => sum + sessionSeconds(item, nowMs), 0)
      const usedWh = items.reduce((sum, item) => sum + Math.max(0, item.used_wh), 0)
      return {
        key: dayKey(items[0].started_at),
        label: dayLabel(items[0].started_at),
        items,
        seconds,
        usedWh,
      }
    })
    .sort((a, b) => b.items[0].started_at - a.items[0].started_at)
}

export function sessionSeconds(session: ReserveSession, nowMs: number): number {
  const end = session.ended_at ?? nowMs / 1000
  return Math.max(0, end - session.started_at)
}

export function pct(value: number): string {
  if (!Number.isFinite(value)) return '—'
  const rounded = Math.round(value * 10) / 10
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}%`
}

export function kwh(wh: number): string {
  const value = Math.max(0, wh) / 1000
  if (value >= 10) return `${value.toFixed(1)} кВт·год`
  return `${value.toFixed(2)} кВт·год`
}

export function power(watts: number): string {
  const value = Math.abs(watts)
  if (value >= 1000) {
    const kw = value / 1000
    return `${kw >= 10 ? kw.toFixed(1) : kw.toFixed(2)} кВт`
  }
  return `${Math.round(value)} Вт`
}

export function duration(seconds: number): string {
  const mins = Math.max(0, Math.round(seconds / 60))
  if (mins < 1) return 'менше хвилини'
  if (mins < 60) return `${mins} хв`
  const hours = Math.floor(mins / 60)
  const rest = mins % 60
  return rest ? `${hours} год ${rest} хв` : `${hours} год`
}

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}

export function sessionsWord(count: number): string {
  const n10 = count % 10
  const n100 = count % 100
  if (n10 === 1 && n100 !== 11) return 'сесія'
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return 'сесії'
  return 'сесій'
}

function dayKey(ts: number): string {
  const date = new Date(ts * 1000)
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

function dayLabel(ts: number): string {
  const date = new Date(ts * 1000)
  const today = new Date()
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const diff = Math.round((startToday - start) / 86_400_000)
  if (diff === 0) return 'Сьогодні'
  if (diff === 1) return 'Вчора'
  return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' })
}
