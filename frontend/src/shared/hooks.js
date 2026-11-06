import { useCallback, useEffect, useRef, useState } from 'react'

// Load data now and every `ms` milliseconds while the page is visible.
export function usePoll(load, ms, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const loadRef = useRef(load)
  loadRef.current = load

  const reload = useCallback(async () => {
    try {
      const d = await loadRef.current()
      setData(d)
      setError(null)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    reload()
    if (!ms) return undefined
    const id = setInterval(() => {
      if (document.visibilityState !== 'hidden') reload()
    }, ms)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading, reload, setData }
}

export function useLocalState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? JSON.parse(raw) : initial
    } catch {
      return initial
    }
  })
  const set = useCallback(
    (v) => {
      setValue(v)
      try {
        if (v === null || v === undefined) localStorage.removeItem(key)
        else localStorage.setItem(key, JSON.stringify(v))
      } catch {
        /* storage unavailable: keep in memory only */
      }
    },
    [key],
  )
  return [value, set]
}
