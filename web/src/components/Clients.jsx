import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../api/client.js'
import { CLIENTS_LIMIT } from '../config.js'
import { KIND_LABEL, shortId } from '../clientId.js'
import Icon from './Icon.jsx'

const formatTime = (iso) =>
  new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

const KIND_FIELD = {
  email: { label: 'Email address', placeholder: 'name@example.com', inputMode: 'email' },
  account: { label: 'Account number', placeholder: '12345678', inputMode: 'numeric' },
  phone: { label: 'Phone number', placeholder: '+49 170 1234567', inputMode: 'tel' },
}

const EMPTY_FORM = { open: false, kind: 'email', value: '', busy: false, error: '', notice: '' }

// Clients page: one row per pseudonymous client, read from GET /clients (BigQuery `clients` view).
// "Add client" sends an email / account number / phone to POST /clients, which stores only its keyed hash.
export default function Clients({ focus = '', onNewTicket }) {
  const [state, setState] = useState({ status: 'loading', configured: true, clients: [], error: '' })
  const [extras, setExtras] = useState([]) // clients added in this session, shown until the list includes them
  const [query, setQuery] = useState(focus)
  const [form, setForm] = useState(EMPTY_FORM)
  const reloadTimer = useRef(null)

  const load = useCallback((signal) => {
    setState((s) => ({ ...s, status: 'loading', error: '' }))
    api
      .listClients(CLIENTS_LIMIT, signal)
      .then((data) => setState({ status: 'ok', configured: data.configured, clients: data.clients, error: '' }))
      .catch((err) => {
        if (err.name !== 'AbortError') setState({ status: 'error', configured: true, clients: [], error: err.message })
      })
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => {
      ctrl.abort()
      clearTimeout(reloadTimer.current)
    }
  }, [load])

  useEffect(() => {
    if (focus) setQuery(focus)
  }, [focus])

  const { status, configured, error } = state

  const rows = useMemo(() => {
    const known = new Set(state.clients.map((c) => c.client_id))
    return [...extras.filter((c) => !known.has(c.client_id)), ...state.clients]
  }, [state.clients, extras])

  const q = query.trim().toLowerCase()
  const visible = useMemo(() => {
    if (!q) return rows
    return rows.filter((c) =>
      [c.client_id, KIND_LABEL[c.id_kind] || c.id_kind, ...(c.languages || []), ...(c.queues || [])]
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [rows, q])

  async function submit(e) {
    e.preventDefault()
    if (!form.value.trim() || form.busy) return
    setForm((f) => ({ ...f, busy: true, error: '', notice: '' }))
    try {
      const res = await api.addClient({ kind: form.kind, value: form.value })
      const now = new Date().toISOString()
      setExtras((x) => [
        { client_id: res.client_id, id_kind: res.id_kind, ticket_count: 0, escalated_count: 0, languages: [], queues: [], first_seen: now, last_seen: now },
        ...x.filter((c) => c.client_id !== res.client_id),
      ])
      setForm({
        ...EMPTY_FORM,
        kind: form.kind,
        notice: res.created ? `Client ${shortId(res.client_id)} added.` : `Client ${shortId(res.client_id)} already exists.`,
      })
      // BigQuery streaming rows can take a moment to show up in queries: refresh shortly after.
      clearTimeout(reloadTimer.current)
      reloadTimer.current = setTimeout(() => load(), 1500)
    } catch (err) {
      setForm((f) => ({ ...f, busy: false, error: err.message }))
    }
  }

  const field = KIND_FIELD[form.kind]

  return (
    <main className="work clients-page">
      <section className="clients" aria-label="Clients" aria-live="polite">
        <div className="clients-head">
          <h2 className="clients-title">Clients</h2>
          {status === 'ok' && configured && (
            <span className="clients-count">{q ? `${visible.length} of ${rows.length}` : rows.length}</span>
          )}
          <button
            type="button"
            className="icon-btn"
            onClick={() => load()}
            disabled={status === 'loading'}
            aria-label="Refresh clients"
            title="Refresh"
          >
            <Icon name="refresh" size={16} />
          </button>
        </div>
        <p className="clients-note">
          Clients are pseudonymous: each id is a keyed hash of the email, account number or phone found in a ticket.
          No personal data is stored.
        </p>

        <div className="clients-toolbar">
          <div className="clients-search">
            <Icon name="search" size={20} />
            <input
              type="search"
              placeholder="Search clients"
              aria-label="Search clients"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
              autoComplete="off"
            />
            {query && (
              <button type="button" className="icon-btn" onClick={() => setQuery('')} aria-label="Clear search">
                <Icon name="close" size={16} />
              </button>
            )}
          </div>
          <button
            type="button"
            className="primary add-btn"
            onClick={() => setForm((f) => ({ ...f, open: !f.open, error: '' }))}
            aria-expanded={form.open}
            disabled={status === 'ok' && !configured}
          >
            <Icon name="plus" size={16} /> Add client
          </button>
        </div>

        {form.open && (
          <form className="add-panel" onSubmit={submit}>
            <div className="add-row">
              <label>
                Identify by
                <select value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value, error: '' }))}>
                  {Object.entries(KIND_LABEL).map(([k, label]) => (
                    <option key={k} value={k}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="grow">
                {field.label}
                <input
                  value={form.value}
                  onChange={(e) => setForm((f) => ({ ...f, value: e.target.value, error: '' }))}
                  placeholder={field.placeholder}
                  inputMode={field.inputMode}
                  autoComplete="off"
                  autoFocus
                />
              </label>
              <button type="submit" className="primary" disabled={form.busy || !form.value.trim()}>
                {form.busy ? 'Adding…' : 'Add'}
              </button>
              <button type="button" onClick={() => setForm(EMPTY_FORM)}>Cancel</button>
            </div>
            <p className="clients-note">The value is hashed on the server and is never stored; only the client id is kept.</p>
            {form.error && (
              <div className="panel error" role="alert">
                <strong>Error:</strong> {form.error}
              </div>
            )}
          </form>
        )}

        {form.notice && (
          <div className="notice" role="status">
            {form.notice}
          </div>
        )}

        {status === 'loading' && rows.length === 0 && <div className="panel muted">Loading clients…</div>}

        {status === 'error' && (
          <div className="panel error" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        {status === 'ok' && !configured && (
          <div className="panel empty">
            <h2>Client registry is not configured</h2>
            <p className="muted">
              Set <code>BQ_DATASET</code> and <code>CLIENT_ID_SALT</code> in the backend <code>.env</code> and restart it.
            </p>
          </div>
        )}

        {status === 'ok' && configured && rows.length === 0 && (
          <div className="panel empty">
            <h2>No clients yet</h2>
            <p className="muted">
              A client appears once an analyzed ticket contains an email, account number or phone, or when you add one.
            </p>
          </div>
        )}

        {rows.length > 0 && visible.length === 0 && (
          <div className="panel empty">
            <h2>No matching clients</h2>
            <p className="muted">Nothing matches “{query.trim()}”.</p>
          </div>
        )}

        {visible.length > 0 && (
          <div className="table-wrap">
            <table className="clients-table">
              <thead>
                <tr>
                  <th scope="col">Client</th>
                  <th scope="col">Identified by</th>
                  <th scope="col" className="num">Tickets</th>
                  <th scope="col" className="num">Escalated</th>
                  <th scope="col">Languages</th>
                  <th scope="col">Queues</th>
                  <th scope="col">First seen</th>
                  <th scope="col">Last seen</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr key={c.client_id}>
                    <td>
                      <span className="client-id" title={c.client_id}>{shortId(c.client_id)}</span>
                    </td>
                    <td>{KIND_LABEL[c.id_kind] || c.id_kind}</td>
                    <td className="num">{c.ticket_count}</td>
                    <td className="num">{c.escalated_count}</td>
                    <td>{(c.languages || []).map((l) => l.toUpperCase()).join(', ') || '–'}</td>
                    <td>{(c.queues || []).join(', ') || '–'}</td>
                    <td className="when">{formatTime(c.first_seen)}</td>
                    <td className="when">{formatTime(c.last_seen)}</td>
                    <td>
                      <button type="button" className="row-btn" onClick={() => onNewTicket?.(c)} title="Write a new ticket as this client">
                        <Icon name="plus" size={14} /> New ticket
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  )
}
