import { useMemo, useState } from 'react'
import Icon from './Icon.jsx'
import manager1 from '../../assets/manager_1.jpg'
import manager2 from '../../assets/manager_2.jpg'

// Demo data: invented names, masked emails (the full address is never shown).
const MANAGERS = [
  {
    id: 'mgr_01',
    name: 'Valeria Montenegro',
    photo: manager1,
    email: 'v•••••••••@sentineldesk.io',
    role: 'Support Operations Manager',
    queues: ['Billing and Payments', 'Customer Service', 'Returns and Exchanges', 'Sales and Pre-Sales', 'General Inquiry', 'Human Resources'],
    languages: ['en'],
    team_size: 8,
    escalations_handled: 42,
    last_active: '2026-11-21T09:12:00',
  },
  {
    id: 'mgr_02',
    name: 'Andrés Valdivia',
    photo: manager2,
    email: 'a•••••••@sentineldesk.io',
    role: 'Escalations Manager',
    queues: ['Technical Support', 'IT Support', 'Product Support', 'Service Outages and Maintenance'],
    languages: ['en', 'de'],
    team_size: 6,
    escalations_handled: 57,
    last_active: '2026-11-21T08:40:00',
  },
]

const formatTime = (iso) =>
  new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

// Managers page: same layout as Clients (title, search, table), listing the two team managers.
export default function Managers() {
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()

  const visible = useMemo(() => {
    if (!q) return MANAGERS
    return MANAGERS.filter((m) =>
      [m.name, m.email, m.role, ...m.queues, ...m.languages].join(' ').toLowerCase().includes(q),
    )
  }, [q])

  return (
    <main className="work clients-page">
      <section className="clients" aria-label="Managers" aria-live="polite">
        <div className="clients-head">
          <h2 className="clients-title">Managers</h2>
          <span className="clients-count">{q ? `${visible.length} of ${MANAGERS.length}` : MANAGERS.length}</span>
        </div>
        <p className="clients-note">
          Managers oversee queues and handle escalations. Email addresses are masked.
        </p>

        <div className="clients-toolbar">
          <div className="clients-search">
            <Icon name="search" size={20} />
            <input
              type="search"
              placeholder="Search managers"
              aria-label="Search managers"
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
        </div>

        {visible.length === 0 && (
          <div className="panel empty">
            <h2>No matching managers</h2>
            <p className="muted">Nothing matches “{query.trim()}”.</p>
          </div>
        )}

        {visible.length > 0 && (
          <div className="table-wrap">
            <table className="clients-table">
              <thead>
                <tr>
                  <th scope="col">Manager</th>
                  <th scope="col">Email</th>
                  <th scope="col">Role</th>
                  <th scope="col" className="num">Team</th>
                  <th scope="col" className="num">Escalations</th>
                  <th scope="col">Languages</th>
                  <th scope="col">Queues</th>
                  <th scope="col">Last active</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <div className="manager-cell">
                        <img className="manager-photo" src={m.photo} alt={m.name} />
                        <span>{m.name}</span>
                      </div>
                    </td>
                    <td><span className="client-id">{m.email}</span></td>
                    <td>{m.role}</td>
                    <td className="num">{m.team_size}</td>
                    <td className="num">{m.escalations_handled}</td>
                    <td>{m.languages.map((l) => l.toUpperCase()).join(', ')}</td>
                    <td>{m.queues.join(', ')}</td>
                    <td className="when">{formatTime(m.last_active)}</td>
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
