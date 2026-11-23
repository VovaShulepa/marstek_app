import { useState } from 'react'
import { BatteryCard } from './components/BatteryCard'
import { EnergyFlow } from './components/EnergyFlow'
import { ActiveAlert, EventLog } from './components/EventLog'
import { HistoryChart } from './components/HistoryChart'
import { ReserveHistory } from './components/ReserveHistory'
import { ReserveJournal } from './components/ReserveJournal'
import { ModeDock } from './components/ModeDock'
import { SettingsModal } from './components/SettingsModal'
import { SimulatorDrawer } from './components/SimulatorDrawer'
import { SelfDrawCard } from './components/SelfDrawCard'
import { StationFacts } from './components/StationFacts'
import { StatsCards } from './components/StatsCards'
import { TopBar } from './components/TopBar'
import { useStation } from './hooks/useStation'

export default function App() {
  const { state, setState, wsStatus } = useStation()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <div className="app-shell" data-state={state.state}>
      <div className="mx-auto flex w-full max-w-lg flex-col gap-5 px-5 pb-32 pt-[max(1rem,env(safe-area-inset-top))]">
        <TopBar state={state} wsStatus={wsStatus} onOpenSettings={() => setSettingsOpen(true)} />
        <BatteryCard state={state} />
        <ActiveAlert state={state} />
        <EnergyFlow state={state} />
        <HistoryChart state={state} />
        <ReserveJournal state={state} onOpenHistory={() => setHistoryOpen(true)} />
        <EventLog state={state} onState={setState} />
        <SelfDrawCard state={state} />
        <StationFacts state={state} />
        <StatsCards state={state} />
      </div>

      {historyOpen && (
        <ReserveHistory state={state} onClose={() => setHistoryOpen(false)} onState={setState} />
      )}
      <ModeDock state={state} onState={setState} />
      <SimulatorDrawer state={state} onState={setState} />
      <SettingsModal
        open={settingsOpen}
        state={state}
        onClose={() => setSettingsOpen(false)}
        onState={setState}
      />
    </div>
  )
}
