import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client.js'
import { REMOTE_HISTORY_LIMIT } from '../config.js'
import { resultWithClient, shortId } from '../clientId.js'
import Icon from './Icon.jsx'

const formatTime = (t) =>
  new Date(t).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

// Maps a GET /tickets row to the shape used by the local history.
const fromStorageRow = (t) => ({
  id: t.ticket_id,
  at: Date.parse(t.received_at),
  subject: t.subject || '',
  body: t.body || '',
  result: resultWithClient(t),
})

// Lists past tickets. Source is Cloud Storage when the backend has it configured,
// otherwise (or if it fails) this browser's local history.
export default function HistoryMenu({ localItems, onClearLocal, onOpen, disabled, storageEnabled }) {
  const [open, setOpen] = useState(false)
  const [remote, setRemote] = useState({ status: 'idle', items: [], error: '' })
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e) => !rootRef.current?.contains(e.target) && setOpen(false)
    const onKeyDown = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onPointerDown)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  // Reload from storage every time the menu opens.
  useEffect(() => {
    if (!open || !storageEnabled) return
    const ctrl = new AbortController()
    setRemote((r) => ({ ...r, status: 'loading', error: '' }))
    api
      .listTickets(REMOTE_HISTORY_LIMIT, ctrl.signal)
      .then((data) => setRemote({ status: 'ok', error: '', items: data.tickets.map(fromStorageRow) }))
      .catch((err) => {
        if (err.name !== 'AbortError') setRemote({ status: 'error', items: [], error: err.message })
      })
    return () => ctrl.abort()
  }, [open, storageEnabled])

  const fromStorage = storageEnabled && remote.status === 'ok'
  const items = fromStorage ? remote.items : localItems
  const loading = storageEnabled && remote.status === 'loading'

  return (
    <div className="history" ref={rootRef}>
      <button
        type="button"
        className="history-btn"
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        History
        <Icon name="chevronDown" size={16} />
      </button>
      {open && (
        <div className="history-menu" role="menu">
          {loading ? (
            <div className="history-empty">Loading tickets from Cloud Storage…</div>
          ) : (
            <>
              {storageEnabled && remote.status === 'error' && (
                <div className="history-empty" role="alert">
                  Could not load from Cloud Storage ({remote.error}). Showing this browser’s history.
                </div>
              )}
              {fromStorage && (
                <div className="history-source">
                  Cloud Storage · {items.length} ticket{items.length === 1 ? '' : 's'}
                </div>
              )}
              {items.length === 0 ? (
                <div className="history-empty">{fromStorage ? 'No tickets in storage yet' : 'No past tickets yet'}</div>
              ) : (
                <div className="history-list">
                  {items.map((h) => (
                    <button
                      type="button"
                      role="menuitem"
                      key={h.id}
                      className="history-item"
                      onClick={() => {
                        setOpen(false)
                        onOpen(h)
                      }}
                    >
                      <span className="history-title">{h.subject.trim() || h.body.trim()}</span>
                      <span className="history-meta">
                        {formatTime(h.at)} · {h.result.priority} · {h.result.escalation.escalate ? 'escalated' : 'drafted'}
                        {h.result.client && ` · ${shortId(h.result.client.client_id)}`}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {!fromStorage && items.length > 0 && (
                <button
                  type="button"
                  className="history-clear"
                  onClick={() => {
                    onClearLocal()
                    setOpen(false)
                  }}
                >
                  Clear history
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
