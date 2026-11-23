import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchState, wsUrl } from '../lib/api'
import { INITIAL_STATE, type StationState } from '../types'

export function useStation() {
  const [state, setState] = useState<StationState>(INITIAL_STATE)
  const [wsStatus, setWsStatus] = useState<'connecting' | 'live' | 'offline'>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)

  const apply = useCallback((payload: unknown) => {
    if (!payload || typeof payload !== 'object') return
    const data = payload as Partial<StationState> & { type?: string }
    if (data.type === 'ping') return
    if (typeof data.soc_pct === 'number') {
      setState((prev) => ({ ...prev, ...data }) as StationState)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined

    const connect = () => {
      if (cancelled) return
      setWsStatus('connecting')
      const ws = new WebSocket(wsUrl())
      wsRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        setWsStatus('live')
      }

      ws.onmessage = (ev) => {
        try {
          apply(JSON.parse(ev.data))
        } catch {
          /* ignore */
        }
      }

      ws.onclose = () => {
        setWsStatus('offline')
        wsRef.current = null
        const delay = Math.min(8000, 500 * 2 ** retryRef.current)
        retryRef.current += 1
        timer = window.setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    // Bootstrap via REST in case WS is slow
    fetchState()
      .then((s) => {
        if (!cancelled) setState(s)
      })
      .catch(() => {
        /* demo UI still renders */
      })

    connect()

    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
      wsRef.current?.close()
    }
  }, [apply])

  return { state, setState, wsStatus }
}
