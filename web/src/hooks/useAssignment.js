import { useEffect, useState } from 'react'
import * as api from '../api/client.js'

// Asks the manager-assignment agent (Gemini, rules fallback) who should take an escalated ticket.
// Pass null when there is no finished analysis. status: idle | loading | ok | error
export default function useAssignment(result) {
  const [state, setState] = useState({ status: 'idle', data: null })
  const escalate = Boolean(result?.escalation?.escalate)
  useEffect(() => {
    if (!escalate) {
      setState({ status: 'idle', data: null })
      return
    }
    const ctrl = new AbortController()
    setState({ status: 'loading', data: null })
    api
      .assignManager(result, ctrl.signal)
      .then((data) => setState({ status: 'ok', data }))
      .catch((err) => err.name !== 'AbortError' && setState({ status: 'error', data: null }))
    return () => ctrl.abort()
  }, [result, escalate])
  return state
}
