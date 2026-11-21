import { useEffect, useState } from 'react'

// useState persisted as JSON in localStorage. Storage can be unavailable (private mode,
// quota), in which case the value simply lives in memory.
export default function useStoredState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw === null ? initial : JSON.parse(raw)
    } catch {
      return initial
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // not persisted
    }
  }, [key, value])

  return [value, setValue]
}
