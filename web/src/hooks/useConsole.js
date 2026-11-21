import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client.js'
import { BULK_PAUSE_MS, BURST_POLL_MS, CLIENTS_LIMIT, MIN_ANALYSIS_MS } from '../config.js'
import { SAMPLES } from '../mocks/samples.js'
import useHistory from './useHistory.js'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const pendingQueue = () => Object.fromEntries(SAMPLES.map((s) => [s.id, 'pending']))

// All console state and actions. App.jsx only lays out what this returns.
//
//   status:  idle | loading | done | error
//   queue:   sample id -> pending | processing | drafted | escalated | error
export default function useConsole() {
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [clientId, setClientId] = useState('') // '' = detect the client from the ticket text
  const [clientList, setClientList] = useState([]) // pseudonymous clients for the picker
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [health, setHealth] = useState(null) // null while loading, false if unreachable
  const [activeSample, setActiveSample] = useState(null)
  const [queue, setQueue] = useState(pendingQueue)
  const [bulk, setBulk] = useState(false)
  const [burst, setBurst] = useState(null) // outage cluster among recent tickets

  // Precedent list controls. Kept here because a draft citation scrolls to a precedent.
  const [highlight, setHighlight] = useState(null)
  const [query, setQuery] = useState('')
  const [minSim, setMinSim] = useState(0)
  const precedentRefs = useRef({})

  const history = useHistory()
  const abortRef = useRef(null)

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth(false))
  }, [])

  const reloadClients = () => api.listClients(CLIENTS_LIMIT).then((d) => setClientList(d.clients || [])).catch(() => {})
  useEffect(() => {
    reloadClients()
  }, [])

  // Outage banner: refreshed on a timer (so it clears when the window passes) and by each triage result.
  useEffect(() => {
    const poll = () => api.getBurst().then(setBurst).catch(() => {})
    poll()
    const id = setInterval(poll, BURST_POLL_MS)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    setQuery('')
    setMinSim(0)
  }, [result])

  const canSubmit = body.trim().length > 0 && status !== 'loading' && !bulk
  const storageEnabled = Boolean(health && health.storage && health.storage.configured)

  async function runTriage(subj, text, signal, client = null) {
    const startedAt = performance.now()
    const data = await api.triage({ subject: subj.trim() ? subj : null, body: text, client }, signal)
    if (data.burst) setBurst(data.burst)
    // MOCK pacing so the stepper is readable; see config.js
    await sleep(Math.max(0, MIN_ANALYSIS_MS - (performance.now() - startedAt)))
    return data
  }

  async function analyze() {
    if (!canSubmit) return
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setStatus('loading')
    setError('')
    setHighlight(null)
    try {
      const picked = clientList.find((c) => c.client_id === clientId) || null
      const data = await runTriage(subject, body, ctrl.signal, picked)
      if (ctrl.signal.aborted) return
      setResult(data)
      setStatus('done')
      history.add(subject, body, data)
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message)
      setStatus('error')
    }
  }

  // Runs every pending sample ticket through the pipeline, one after another.
  async function answerAll() {
    if (bulk) return
    abortRef.current?.abort()
    setBulk(true)
    for (const sample of SAMPLES.filter((s) => queue[s.id] === 'pending')) {
      setQueue((q) => ({ ...q, [sample.id]: 'processing' }))
      loadSample(sample)
      setStatus('loading')
      setError('')
      setHighlight(null)
      try {
        const data = await runTriage(sample.subject, sample.body)
        setResult(data)
        setStatus('done')
        history.add(sample.subject, sample.body, data)
        setQueue((q) => ({ ...q, [sample.id]: data.escalation.escalate ? 'escalated' : 'drafted' }))
      } catch (err) {
        setError(err.message)
        setStatus('error')
        setQueue((q) => ({ ...q, [sample.id]: 'error' }))
      }
      await sleep(BULK_PAUSE_MS)
    }
    setBulk(false)
  }

  function loadSample(sample) {
    setSubject(sample.subject)
    setBody(sample.body)
    setActiveSample(sample.id)
  }

  // Re-open a past ticket with the result it already has; nothing is re-analyzed.
  function openPast(entry) {
    abortRef.current?.abort()
    setSubject(entry.subject)
    setBody(entry.body)
    setActiveSample(null)
    setHighlight(null)
    setError('')
    setResult(entry.result)
    setStatus('done')
  }

  // Back to a blank form with no ticket open.
  function clear() {
    abortRef.current?.abort()
    setClientId('')
    setSubject('')
    setBody('')
    setActiveSample(null)
    setHighlight(null)
    setError('')
    setResult(null)
    setStatus('idle')
  }

  // Filters are cleared first so the cited precedent is guaranteed to be in the list.
  function jumpToPrecedent(id) {
    setQuery('')
    setMinSim(0)
    setHighlight(id)
    setTimeout(() => precedentRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60)
  }

  const counts = {
    pending: SAMPLES.filter((s) => queue[s.id] === 'pending').length,
    drafted: SAMPLES.filter((s) => queue[s.id] === 'drafted').length,
    escalated: SAMPLES.filter((s) => queue[s.id] === 'escalated').length,
  }

  return {
    // form
    subject, setSubject, body, setBody, canSubmit, analyze, clear,
    clientId, setClientId, clientList, reloadClients,
    // outcome
    status, result, error,
    // samples and queue
    samples: SAMPLES, activeSample, loadSample, queue, counts, bulk, answerAll,
    resetQueue: () => setQueue(pendingQueue()),
    // precedents
    highlight, query, setQuery, minSim, setMinSim, precedentRefs, jumpToPrecedent,
    // history
    history, openPast,
    // backend status
    health, storageEnabled,
    // outage detection
    burst,
  }
}
