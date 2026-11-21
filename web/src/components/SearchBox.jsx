import { useEffect, useId, useMemo, useRef, useState } from 'react'
import * as api from '../api/client.js'
import { resultWithClient, shortId } from '../clientId.js'
import { REMOTE_HISTORY_LIMIT } from '../config.js'
import geminiLogo from '../../assets/gemini_logo.webp'

const MAX_RESULTS = 8

const formatTime = (t) =>
  new Date(t).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

// Same mapping as HistoryMenu: a GET /tickets row -> the shape used by the local history.
const fromStorageRow = (t) => ({
  id: t.ticket_id,
  at: Date.parse(t.received_at),
  subject: t.subject || '',
  body: t.body || '',
  result: resultWithClient(t),
})

// Search over past tickets (Cloud Storage when configured, otherwise this browser's history).
// Press "/" anywhere to focus it, arrows + Enter to pick a result, Esc to clear.
export default function SearchBox({ storageEnabled, localItems, onOpen }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [remote, setRemote] = useState({ status: 'idle', items: [] })
  const inputRef = useRef(null)
  const rootRef = useRef(null)
  const listId = useId()

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target
      if (t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return
      e.preventDefault()
      inputRef.current?.focus()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e) => !rootRef.current?.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  // Refresh the stored tickets every time the box opens.
  useEffect(() => {
    if (!open || !storageEnabled) return
    const ctrl = new AbortController()
    setRemote((r) => ({ ...r, status: 'loading' }))
    api
      .listTickets(REMOTE_HISTORY_LIMIT, ctrl.signal)
      .then((data) => setRemote({ status: 'ok', items: data.tickets.map(fromStorageRow) }))
      .catch((err) => {
        if (err.name !== 'AbortError') setRemote({ status: 'error', items: [] })
      })
    return () => ctrl.abort()
  }, [open, storageEnabled])

  const source = storageEnabled && remote.status === 'ok' ? remote.items : localItems
  const q = query.trim().toLowerCase()
  const results = useMemo(() => {
    if (!q) return []
    return source
      .filter((t) =>
        [t.subject, t.body, t.result?.queue, t.result?.type, t.result?.priority, t.result?.client?.client_id].some((v) =>
          String(v || '').toLowerCase().includes(q),
        ),
      )
      .slice(0, MAX_RESULTS)
  }, [q, source])

  useEffect(() => setActive(0), [q])

  function pick(item) {
    setOpen(false)
    setQuery('')
    inputRef.current?.blur()
    onOpen(item)
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown' && results.length) {
      e.preventDefault()
      setActive((a) => (a + 1) % results.length)
    } else if (e.key === 'ArrowUp' && results.length) {
      e.preventDefault()
      setActive((a) => (a - 1 + results.length) % results.length)
    } else if (e.key === 'Enter' && results[active]) {
      e.preventDefault()
      pick(results[active])
    } else if (e.key === 'Escape') {
      if (query) setQuery('')
      else {
        setOpen(false)
        inputRef.current?.blur()
      }
    }
  }

  const showPanel = open
  const loading = storageEnabled && remote.status === 'loading'

  return (
    <div className="search" ref={rootRef}>
      <img className="search-icon" src={geminiLogo} alt="" width="20" height="20" />
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-expanded={showPanel && q !== ''}
        aria-controls={listId}
        aria-activedescendant={results[active] ? `${listId}-${active}` : undefined}
        aria-label="Search past tickets"
        placeholder="Search tickets"
        value={query}
        autoComplete="off"
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {!query && <kbd className="search-key" aria-hidden="true">/</kbd>}

      {showPanel && (
        <div className="search-panel" id={listId} role="listbox">
          {!q && <div className="search-hint">Search past tickets by subject, text, queue, type, priority or client id.</div>}
          {q && loading && results.length === 0 && <div className="search-hint">Searching stored tickets…</div>}
          {q && !loading && results.length === 0 && <div className="search-hint">No matching tickets.</div>}
          {results.map((t, i) => (
            <button
              type="button"
              role="option"
              id={`${listId}-${i}`}
              key={t.id}
              aria-selected={i === active}
              className={`search-item ${i === active ? 'active' : ''}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(t)}
            >
              <span className="search-title">{t.subject.trim() || t.body.trim()}</span>
              <span className="search-meta">
                {formatTime(t.at)} · {t.result.queue} · {t.result.priority}
                {t.result.client && ` · ${shortId(t.result.client.client_id)}`}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
