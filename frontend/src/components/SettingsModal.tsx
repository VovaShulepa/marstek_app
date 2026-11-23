import { X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { discoverDevices, updateConfig, updateDevice, updateSchedule } from '../lib/api'
import { POWER_VERSIONS, WEEKDAYS, type DiscoveredDevice, type ManualSlot, type StationState } from '../types'

interface Props {
  open: boolean
  state: StationState
  onClose: () => void
  onState: (s: StationState) => void
}

const EMPTY_SLOT: ManualSlot = {
  time_num: 0,
  start_time: '00:00',
  end_time: '06:00',
  week_set: 31,
  power_w: -800,
  enable: true,
}

export function SettingsModal({ open, state, onClose, onState }: Props) {
  const [ip, setIp] = useState(state.station_ip)
  const [port, setPort] = useState(String(state.station_port))
  const [eff, setEff] = useState(String(Math.round(state.inverter_efficiency * 100)))
  const [demo, setDemo] = useState(state.demo_mode)
  const [dod, setDod] = useState(state.dod_pct)
  const [slot, setSlot] = useState<ManualSlot>(EMPTY_SLOT)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [found, setFound] = useState<DiscoveredDevice[]>([])
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    if (!open) return
    setIp(state.station_ip)
    setPort(String(state.station_port))
    setEff(String(Math.round(state.inverter_efficiency * 100)))
    setDemo(state.demo_mode)
    setDod(state.dod_pct)
    setSlot(state.schedules[0] ?? { ...EMPTY_SLOT, power_w: -Math.min(800, state.power_version_w || 800) })
    setMsg('')
    setFound([])
    // Form opens from the current snapshot and must not reset on the next live tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  if (!open) return null

  const saveLink = async () => {
    setSaving(true)
    setMsg('')
    try {
      const res = await updateConfig({
        marstek_ip: ip.trim(),
        marstek_port: Number(port) || 30000,
        inverter_efficiency: (Number(eff) || 95) / 100,
        demo_mode: demo,
      })
      if (res.state) onState(res.state)
      setMsg('Зв’язок збережено')
    } catch {
      setMsg('Не вдалося зберегти зв’язок')
    } finally {
      setSaving(false)
    }
  }

  const scan = async () => {
    setScanning(true)
    setMsg('')
    try {
      const res = await discoverDevices()
      setFound(res.devices)
      setMsg(res.message)
    } catch {
      setMsg('Пошук не вдався')
    } finally {
      setScanning(false)
    }
  }

  const pushDevice = async (body: Parameters<typeof updateDevice>[0], label: string) => {
    setMsg('')
    try {
      const res = await updateDevice(body)
      if (res.state) {
        onState(res.state)
        setDod(res.state.dod_pct)
      }
      setMsg(res.message || label)
    } catch {
      setMsg('Станція не відповіла')
    }
  }

  const pushSlot = async () => {
    setMsg('')
    try {
      const res = await updateSchedule(slot)
      if (res.state) onState(res.state)
      setMsg(res.message)
    } catch {
      setMsg('Розклад не надіслано')
    }
  }

  const watts = Math.abs(slot.power_w) || 0
  const charging = slot.power_w < 0

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center">
      <div className="glass flex max-h-[88dvh] w-full max-w-md flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 pb-2 pt-5">
          <h2 className="text-lg font-semibold text-white">Налаштування станції</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-slate-400 hover:bg-white/10 hover:text-white"
            aria-label="Закрити"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 overflow-y-auto px-5 pb-5">
          <p className="text-[12px] leading-relaxed text-white/45">
            По UDP станція віддає режими Самоспоживання, AI, Ручний, Пасивний і UPS, глибину розряду,
            ліміт потужності, LED, Bluetooth, лічильник CT і сумарну енергію. Тарифи, хмарний графік AI
            і напруги комірок лишаються в офіційному додатку Marstek.
          </p>

          <Section title="Станція">
            <Info label="Wi‑Fi" value={state.wifi_ssid || 'немає мережі'} hint={state.wifi_rssi == null ? '' : `${state.wifi_rssi} дБм`} />
            <Info label="Модель" value={`${state.device_model || 'Venus E'}${state.firmware != null ? ` · FW ${state.firmware}` : ''}`} />
            <Info label="З мережі" value={`${state.total_grid_import_kwh.toFixed(1)} кВт·год`} />
            <Info label="У мережу" value={`${state.total_grid_export_kwh.toFixed(1)} кВт·год`} />
            <Info label="Дім, всього" value={`${state.total_load_kwh.toFixed(1)} кВт·год`} />
            <Info label="CT" value={state.ct_connected ? `${Math.round(state.ct_power_w)} Вт` : 'не підключений'} />
            <Info label="Мова інтерфейсу" value="Українська" />
            <p className="text-[11px] leading-snug text-white/35">
              Тариф, скидання до заводу, шаринг і відгук лишаються в офіційному Marstek: станція їх по UDP не приймає.
            </p>
          </Section>

          <Section title="Глибина розряду">
            <div className="flex items-baseline justify-between">
              <p className="text-[28px] font-semibold tabular-nums text-white">{dod}%</p>
              <p className="text-[12px] text-white/45">резерв {100 - dod}%</p>
            </div>
            <input
              type="range"
              min={30}
              max={88}
              step={1}
              value={dod}
              onChange={(e) => setDod(Number(e.target.value))}
              className="mt-2 w-full"
              aria-label="Глибина розряду"
            />
            <p className="mt-1 text-[11px] leading-snug text-white/35">
              Станція приймає DOD від 30 до 88 і не віддає поточне значення назад. Повзунок пам’ятає
              те, що надіслали звідси. Заводське — 88, резерв 12%.
            </p>
            <button type="button" className="btn-primary mt-3" onClick={() => pushDevice({ dod_pct: dod }, 'DOD')}>
              Надіслати DOD
            </button>
          </Section>

          <Section title="Ручний розклад">
            <div className="flex flex-wrap gap-1.5">
              {Array.from({ length: 10 }, (_, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => {
                    const saved = state.schedules.find((item) => item.time_num === index)
                    setSlot(saved ?? { ...EMPTY_SLOT, time_num: index })
                  }}
                  className={`rounded-full px-2.5 py-1 text-[11px] ${
                    slot.time_num === index ? 'bg-white/15 text-white' : 'bg-white/5 text-white/45'
                  }`}
                >
                  {index + 1}
                </button>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Field label="Початок">
                <input
                  type="time"
                  value={slot.start_time}
                  onChange={(e) => setSlot({ ...slot, start_time: e.target.value })}
                  className="field-input"
                />
              </Field>
              <Field label="Кінець">
                <input
                  type="time"
                  value={slot.end_time}
                  onChange={(e) => setSlot({ ...slot, end_time: e.target.value })}
                  className="field-input"
                />
              </Field>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {WEEKDAYS.map((day, index) => {
                const on = (slot.week_set & (1 << index)) !== 0
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => setSlot({ ...slot, week_set: slot.week_set ^ (1 << index) })}
                    className={`rounded-full px-2.5 py-1 text-[11px] ${on ? 'bg-[#22d068]/20 text-[#b6f5d0]' : 'bg-white/5 text-white/40'}`}
                  >
                    {day}
                  </button>
                )
              })}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => setSlot({ ...slot, power_w: -Math.abs(watts || 800) })}
                className={`flex-1 rounded-xl py-2 text-[12px] ${charging ? 'bg-white/15 text-white' : 'bg-white/5 text-white/45'}`}
              >
                Заряд
              </button>
              <button
                type="button"
                onClick={() => setSlot({ ...slot, power_w: Math.abs(watts || 800) })}
                className={`flex-1 rounded-xl py-2 text-[12px] ${!charging ? 'bg-white/15 text-white' : 'bg-white/5 text-white/45'}`}
              >
                Розряд
              </button>
            </div>
            <Field label="Потужність, Вт">
              <input
                value={String(watts)}
                onChange={(e) => {
                  const next = Math.max(0, Math.min(state.power_version_w || 2500, Number(e.target.value) || 0))
                  setSlot({ ...slot, power_w: charging ? -next : next })
                }}
                inputMode="numeric"
                className="field-input mt-1.5"
              />
            </Field>
            <label className="mt-3 flex items-center justify-between text-sm text-slate-300">
              <span>Вікно увімкнене</span>
              <input
                type="checkbox"
                checked={slot.enable}
                onChange={(e) => setSlot({ ...slot, enable: e.target.checked })}
                className="h-4 w-4 accent-[#22d068]"
              />
            </label>
            <p className="mt-2 text-[11px] leading-snug text-white/35">
              Додатне значення розряджає батарею в дім, від’ємне заряджає з мережі. Вікон може бути десять.
              Станція не показує вже записаний розклад, тож список нижче — те, що надіслали з цього додатка.
            </p>
            <button type="button" className="btn-primary mt-3" onClick={pushSlot}>
              Надіслати вікно {slot.time_num + 1}
            </button>
            {state.schedules.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {state.schedules.map((item) => (
                  <li key={item.time_num}>
                    <button
                      type="button"
                      onClick={() => setSlot(item)}
                      className="w-full rounded-xl bg-black/20 px-3 py-2 text-left text-[12px] text-white/70"
                    >
                      Вікно {item.time_num + 1} · {item.start_time}–{item.end_time} ·{' '}
                      {item.power_w < 0 ? 'заряд' : 'розряд'} {Math.abs(item.power_w)} Вт
                      {item.enable ? '' : ' · вимкнене'}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Корпус і мережа">
            <Choice
              label="LED"
              hint={
                state.led_on == null
                  ? 'Світлодіод на корпусі. Ще не надсилали звідси'
                  : state.led_on
                    ? 'Світиться'
                    : 'Погашений'
              }
              onLabel="Увімкнути"
              offLabel="Вимкнути"
              value={state.led_on}
              lamp
              onChange={(led_on) => pushDevice({ led_on }, 'LED')}
            />
            <Choice
              label="Bluetooth поруч"
              hint={
                state.ble_state
                  ? `Зв’язок: ${state.ble_state}`
                  : state.ble_broadcast == null
                    ? 'Ще не надсилали з цього додатка'
                    : state.ble_broadcast
                      ? 'Трансляція увімкнена'
                      : 'Трансляцію заблоковано'
              }
              onLabel="Показувати"
              offLabel="Сховати"
              value={state.ble_broadcast}
              onChange={(ble_broadcast) => pushDevice({ ble_broadcast }, 'Bluetooth')}
            />
            <p className="text-[11px] uppercase tracking-wider text-white/35">Клас потужності</p>
            <div className="flex flex-wrap gap-1.5">
              {POWER_VERSIONS.map((wattsOption) => (
                <button
                  key={wattsOption}
                  type="button"
                  onClick={() => pushDevice({ power_version_w: wattsOption }, 'Потужність')}
                  className={`rounded-full px-2.5 py-1 text-[11px] ${
                    state.power_version_w === wattsOption ? 'bg-white/15 text-white' : 'bg-white/5 text-white/45'
                  }`}
                >
                  {wattsOption} Вт
                </button>
              ))}
            </div>
            <p className="text-[11px] leading-snug text-white/35">
              Для Venus E заводський клас — 2500 Вт. Менше значення ріже заряд і розряд на самій станції.
            </p>
          </Section>

          <Section title="Зв’язок">
            <button type="button" className="btn-ghost w-full" onClick={scan} disabled={scanning}>
              {scanning ? 'Шукаю в мережі…' : 'Знайти станцію'}
            </button>
            {found.length > 0 && (
              <div className="space-y-1.5">
                {found.map((device) => (
                  <button
                    key={device.wifi_mac || device.ip}
                    type="button"
                    onClick={() => setIp(device.ip)}
                    className="w-full rounded-xl bg-black/20 px-3 py-2 text-left text-[12px] text-white/75"
                  >
                    {device.model || 'Marstek'} · {device.ip}
                    {device.firmware != null ? ` · FW ${device.firmware}` : ''}
                  </button>
                ))}
              </div>
            )}
            <Field label="IP станції">
              <input value={ip} onChange={(e) => setIp(e.target.value)} className="field-input" placeholder="192.168.1.100" />
            </Field>
            <Field label="UDP порт">
              <input value={port} onChange={(e) => setPort(e.target.value)} className="field-input" inputMode="numeric" />
            </Field>
            <Field label="ККД для розрахунку часу, %">
              <input value={eff} onChange={(e) => setEff(e.target.value)} className="field-input" inputMode="decimal" />
            </Field>
            <label className="flex items-center justify-between rounded-xl border border-white/8 bg-black/20 px-3 py-3 text-sm text-slate-300">
              <span>DEMO режим</span>
              <input
                type="checkbox"
                checked={demo}
                onChange={(e) => setDemo(e.target.checked)}
                className="h-4 w-4 accent-[#22d068]"
              />
            </label>
            <button type="button" className="btn-primary" disabled={saving} onClick={saveLink}>
              {saving ? 'Збереження…' : 'Зберегти зв’язок'}
            </button>
          </Section>

          {msg && <p className="text-center text-sm text-[#b6f5d0]">{msg}</p>}
        </div>
      </div>

      <style>{`
        .field-input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid rgba(255,255,255,0.08);
          background: rgba(6, 14, 24, 0.35);
          padding: 0.65rem 0.85rem;
          color: #f1f5f9;
          color-scheme: dark;
          font-size: 0.875rem;
          outline: none;
        }
        .field-input:focus { border-color: rgba(34,208,104,0.45); }
        .btn-primary, .btn-ghost {
          width: 100%;
          border-radius: 0.85rem;
          padding: 0.7rem 0.85rem;
          font-size: 0.875rem;
          font-weight: 600;
        }
        .btn-primary { background: #22d068; color: #06210f; }
        .btn-primary:disabled { opacity: 0.5; }
        .btn-ghost {
          background: rgba(255,255,255,0.06);
          color: #e2e8f0;
        }
      `}</style>
    </div>
  )
}

function Info({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-black/20 px-3 py-2.5">
      <span className="text-[13px] text-white/55">{label}</span>
      <span className="truncate text-right text-[13px] font-medium text-white">
        {value}
        {hint ? <span className="ml-1 font-normal text-white/40">{hint}</span> : null}
      </span>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2.5">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/40">{title}</h3>
      {children}
    </section>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs uppercase tracking-wider text-slate-500">{label}</span>
      {children}
    </label>
  )
}

function Choice({
  label,
  hint,
  onLabel,
  offLabel,
  value,
  lamp,
  onChange,
}: {
  label: string
  hint: string
  onLabel: string
  offLabel: string
  value: boolean | null
  lamp?: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <div className="rounded-xl border border-white/8 bg-black/20 px-3 py-3">
      <p className="flex items-center gap-2 text-sm text-slate-200">
        {lamp && (
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{
              background: value ? '#22d068' : 'rgba(255,255,255,0.28)',
              boxShadow: value ? '0 0 8px #22d068' : 'none',
            }}
          />
        )}
        {label}
      </p>
      <p className="mt-1 text-[11px] leading-snug text-white/35">{hint}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`flex-1 rounded-lg py-1.5 text-[12px] ${value === true ? 'bg-white/15 text-white' : 'bg-white/5 text-white/45'}`}
        >
          {onLabel}
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`flex-1 rounded-lg py-1.5 text-[12px] ${value === false ? 'bg-white/15 text-white' : 'bg-white/5 text-white/45'}`}
        >
          {offLabel}
        </button>
      </div>
    </div>
  )
}
