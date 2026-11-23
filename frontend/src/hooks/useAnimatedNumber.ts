import { useEffect, useRef, useState } from 'react'

/** Smoothly interpolates a number toward `value`. */
export function useAnimatedNumber(value: number, precision = 0, durationMs = 820) {
  const [display, setDisplay] = useState(value)
  const displayRef = useRef(value)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    const from = displayRef.current
    const to = value
    if (from === to || Number.isNaN(to)) {
      displayRef.current = to
      setDisplay(to)
      return
    }

    const start = performance.now()
    const factor = 10 ** precision

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      // easeOut cubic
      const eased = 1 - (1 - t) ** 3
      const next = from + (to - from) * eased
      const rounded = Math.round(next * factor) / factor
      displayRef.current = rounded
      setDisplay(rounded)
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        displayRef.current = to
        setDisplay(to)
      }
    }

    if (frameRef.current) cancelAnimationFrame(frameRef.current)
    frameRef.current = requestAnimationFrame(tick)

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
  }, [value, precision, durationMs])

  return display
}
