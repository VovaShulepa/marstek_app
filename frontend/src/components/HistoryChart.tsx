import { motion } from 'framer-motion'
import { useMemo } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { StationState } from '../types'

interface Props {
  state: StationState
}

interface Row {
  t: string
  power: number
  charge: number | null
  discharge: number | null
}

function PowerTip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ payload: Row }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  const power = payload[0].payload.power
  const charging = power > 30
  const discharging = power < -30
  const title = charging ? 'Заряд' : discharging ? 'Розряд' : 'Тиша'
  const color = charging ? '#22d068' : discharging ? '#f6a323' : '#9aa6b5'
  return (
    <div
      style={{
        background: 'rgba(12, 16, 24, 0.92)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 12,
        padding: '8px 10px',
        fontSize: 12,
      }}
    >
      <div style={{ color: '#94a3b8', marginBottom: 2 }}>{label}</div>
      <div style={{ color, fontWeight: 600 }}>
        {title} · {Math.abs(power)} Вт
      </div>
    </div>
  )
}

export function HistoryChart({ state }: Props) {
  const data = useMemo<Row[]>(
    () =>
      state.history.map((point) => {
        const signed = Math.round(point.power_w)
        const watts = Math.abs(signed)
        return {
          t: new Date(point.ts * 1000).toLocaleTimeString('uk-UA', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          power: signed,
          charge: signed > 0 ? watts : null,
          discharge: signed < 0 ? watts : null,
        }
      }),
    [state.history],
  )

  const livePower = data.length ? data[data.length - 1].power : Math.round(state.battery_power_w)
  const liveCharging = livePower > 30
  const liveDischarging = livePower < -30
  const liveColor = liveCharging ? '#22d068' : liveDischarging ? '#f6a323' : '#9aa6b5'
  const liveLabel = liveCharging ? 'заряд' : liveDischarging ? 'розряд' : 'тиша'
  const peak = Math.max(0, ...data.map((row) => Math.max(row.charge ?? 0, row.discharge ?? 0)))
  const domain: [number, number] = [0, Math.max(200, Math.ceil(peak * 1.12))]

  return (
    <motion.section
      className="glass px-3.5 py-4 sm:px-4"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.14, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="mb-3 flex items-start justify-between gap-3 px-0.5">
        <div>
          <h2 className="text-[13px] font-medium tracking-[0.01em] text-white/55">Потужність</h2>
          <div className="mt-1 flex items-center gap-3 text-[11px] text-white/40">
            <span className="inline-flex items-center gap-1.5 font-medium text-[#f6a323]">
              <i className="h-1.5 w-1.5 rounded-full bg-[#f6a323]" />
              Розряд
            </span>
            <span className="inline-flex items-center gap-1.5 font-medium text-[#22d068]">
              <i className="h-1.5 w-1.5 rounded-full bg-[#22d068]" />
              Заряд
            </span>
            <span>24 год</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[15px] font-semibold tabular-nums" style={{ color: liveColor }}>
            {Math.abs(livePower)} Вт
          </div>
          <div className="text-[11px] text-white/35">
            зараз · <span style={{ color: liveColor }}>{liveLabel}</span>
          </div>
        </div>
      </div>

      <div className="h-52 w-full">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-600">
            Збираємо дані…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="chargeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d068" stopOpacity={0.55} />
                  <stop offset="100%" stopColor="#22d068" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="dischargeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f6a323" stopOpacity={0.55} />
                  <stop offset="100%" stopColor="#f6a323" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="t"
                tick={{ fill: '#64748B', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                minTickGap={42}
              />
              <YAxis
                domain={domain}
                tick={{ fill: '#64748B', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={34}
                tickCount={5}
                tickFormatter={(value: number) => {
                  const n = Math.round(value)
                  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}к`
                  return `${n}`
                }}
              />
              <Tooltip content={<PowerTip />} />
              <Area
                type="monotone"
                dataKey="charge"
                connectNulls={false}
                name="Заряд"
                stroke="#22d068"
                fill="url(#chargeFill)"
                strokeWidth={2}
                baseValue={0}
                dot={false}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="discharge"
                connectNulls={false}
                name="Розряд"
                stroke="#f6a323"
                fill="url(#dischargeFill)"
                strokeWidth={2}
                baseValue={0}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </motion.section>
  )
}
