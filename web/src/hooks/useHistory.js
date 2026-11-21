import { LOCAL_HISTORY_MAX, STORAGE_KEYS } from '../config.js'
import useStoredState from './useStoredState.js'

// Tickets analyzed in this browser, newest first. This is the fallback shown in the History
// menu when Cloud Storage is not configured; with storage on, the menu reads /tickets instead.
export default function useHistory() {
  const [items, setItems] = useStoredState(STORAGE_KEYS.history, [])

  function add(subject, body, result) {
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      at: Date.now(),
      subject,
      body,
      result,
    }
    setItems((prev) => [entry, ...prev].slice(0, LOCAL_HISTORY_MAX))
  }

  return { items, add, clear: () => setItems([]) }
}
