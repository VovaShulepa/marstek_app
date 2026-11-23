import { Battery, ChevronLeft, Settings } from 'lucide-react'
import { openEvents } from './EventLog'
import type { StationState } from '../types'

interface Props {
  state: StationState
  wsStatus: 'connecting' | 'live' | 'offline'
  onOpenSettings: () => void
}

export function TopBar({ state, wsStatus, onOpenSettings }: Props) {
  const live = state.demo_mode || (wsStatus === 'live' && state.connected)

  return (
    <header className="flex items-center justify-between px-0.5">
      <div className="flex min-w-0 items-center gap-1.5">
        <ChevronLeft className="h-5 w-5 shrink-0 text-white/70" />
        <h1 className="truncate text-[16px] font-semibold tracking-[-0.02em] text-white">
          Marstek Venus E 3.0
        </h1>
        <Battery className={`h-4 w-4 shrink-0 ${live ? 'text-[#22d068]' : 'text-slate-500'}`} />
        {state.demo_mode && (
          <span className="rounded-md bg-white/8 px-1.5 py-0.5 text-[10px] font-medium text-white/70">
            DEMO
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {openEvents(state).length > 0 && (
          <button
            type="button"
            onClick={() => document.getElementById('event-log')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            className={`rounded-full border px-2 py-1 text-[12px] font-semibold ${
              openEvents(state).some((event) => event.level === 'error')
                ? 'border-[#ff5d5d]/40 bg-[#ff5d5d]/15 text-[#ff5d5d]'
                : 'border-[#f6a323]/40 bg-[#f6a323]/15 text-[#f6a323]'
            }`}
            aria-label="Журнал попереджень"
          >
            {openEvents(state).length}
          </button>
        )}
        <button
          type="button"
          onClick={onOpenSettings}
          className="rounded-full border border-white/10 bg-white/5 p-2 text-white/75 backdrop-blur-md transition hover:bg-white/10 hover:text-white"
          aria-label="Налаштування"
        >
          <Settings className="h-[18px] w-[18px]" />
        </button>
      </div>
    </header>
  )
}
