import { useCallback, useMemo } from "react"
import { useSearchParams } from "react-router-dom"

import { readRange, writeRange, type RangePreset, type TimeRangeValue } from "../lib/timeRange"

/**
 * Filter state kept in the URL (P7.5 batch 4d), so Back and Forward work and a pasted link opens
 * the same view. The URL carries no authority: whoever opens it still sees only what their own
 * session, role and organization allow.
 *
 * A value outside `allowed` reads as the fallback, and the fallback itself is left out of the URL.
 * Discrete choices add a history entry; typing (`replace: true`) does not.
 */
export function useUrlParam(
  key: string,
  fallback: string,
  allowed?: readonly string[],
): [string, (value: string, options?: { replace?: boolean }) => void] {
  const [params, setParams] = useSearchParams()
  const raw = params.get(key)
  const value = raw !== null && (!allowed || allowed.includes(raw)) ? raw : fallback
  const setValue = useCallback(
    (next: string, options?: { replace?: boolean }) => {
      setParams((current) => {
        const updated = new URLSearchParams(current)
        if (next === fallback || next === "") updated.delete(key)
        else updated.set(key, next)
        return updated
      }, { replace: options?.replace ?? false })
    },
    [fallback, key, setParams],
  )
  return [value, setValue]
}

export function useTimeRangeParam(fallback: RangePreset): [TimeRangeValue, (value: TimeRangeValue) => void] {
  const [params, setParams] = useSearchParams()
  const serialized = params.toString()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- the string is the identity of params
  const value = useMemo(() => readRange(new URLSearchParams(serialized), fallback), [serialized, fallback])
  const setValue = useCallback(
    (next: TimeRangeValue) => setParams((current) => writeRange(current, next, fallback)),
    [fallback, setParams],
  )
  return [value, setValue]
}

/** Every filter key a page owns, for "Clear filters": drops them, keeps anything else in the URL. */
export function useClearUrlParams(keys: readonly string[]): () => void {
  const [, setParams] = useSearchParams()
  return useCallback(() => {
    setParams((current) => {
      const updated = new URLSearchParams(current)
      for (const key of keys) updated.delete(key)
      return updated
    })
  }, [keys, setParams])
}
