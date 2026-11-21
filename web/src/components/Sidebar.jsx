import { OPERATOR } from '../config.js'
import Icon from './Icon.jsx'

const STATUS_TAG = {
  processing: '… Processing',
  drafted: '✓ Drafted',
  escalated: '▲ Escalated',
  error: '! Error',
}

// Storage line at the bottom of the sidebar, derived from GET /health.
function storageStatus(health) {
  if (health === null) return { text: 'Checking storage…' }
  if (health && health.storage && health.storage.configured) return { bucket: health.storage.bucket }
  return { text: 'Storage not configured' }
}

export default function Sidebar({ collapsed, onToggle, console: c }) {
  const storage = storageStatus(c.health)
  const storageTitle = storage.bucket ? `DB at ${storage.bucket}` : storage.text
  const total = c.samples.length

  if (collapsed) {
    return (
      <aside className="sidebar collapsed" aria-label="Navigation">
        <button type="button" className="rail-btn sidebar-toggle" onClick={onToggle} aria-label="Expand sidebar" title="Expand sidebar">
          <Icon name="expand" />
        </button>
        <nav className="rail">
          <div className="rail-btn active" title="Triage console" aria-current="page">
            <Icon name="home" strokeWidth={1.8} />
          </div>
          <button
            type="button"
            className="rail-btn"
            disabled={c.counts.pending === 0 || c.bulk}
            onClick={c.answerAll}
            aria-label="Answer all pending tickets"
            title={`Answer all (${c.counts.pending}/${total} pending)`}
          >
            <Icon name="checks" strokeWidth={1.8} />
            {c.counts.pending > 0 && <span className="rail-badge">{c.counts.pending}</span>}
          </button>
          <div className="rail-sep" />
          {c.samples.map((s) => (
            <button
              type="button"
              key={s.id}
              className={`rail-btn ${c.activeSample === s.id ? 'active' : ''}`}
              onClick={() => c.loadSample(s)}
              disabled={c.bulk}
              aria-label={s.label}
              title={s.label}
            >
              <Icon name="ticket" strokeWidth={1.8} />
              {c.queue[s.id] !== 'pending' && <span className={`rail-dot ${c.queue[s.id]}`} />}
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <div className="rail-btn" title={storageTitle}><Icon name="db" strokeWidth={1.8} /></div>
          <div className="rail-btn" title={`${OPERATOR.name} · ${OPERATOR.role}`}><Icon name="user" strokeWidth={1.8} /></div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="sidebar" aria-label="Navigation">
      <div className="brand">
        <span className="brand-a">Sentinel</span><span className="brand-b">Desk</span>
        <button type="button" className="icon-btn brand-toggle sidebar-toggle" onClick={onToggle} aria-label="Collapse sidebar" title="Collapse sidebar">
          <Icon name="collapse" />
        </button>
      </div>

      <nav>
        <div className="nav-label">Main</div>
        <div className="nav-item active" aria-current="page">Triage console</div>

        <div className="nav-label">Queue</div>
        <div className="queue">
          <div className="queue-row">
            <div className="queue-count">
              <strong>{c.counts.pending}/{total}</strong>
              <span>pending</span>
            </div>
            <button
              type="button"
              className="icon-btn"
              disabled={c.counts.pending === 0 || c.bulk}
              onClick={c.answerAll}
              aria-label="Answer all pending tickets"
              title={c.bulk ? 'Answering…' : 'Answer all'}
            >
              <Icon name="checks" size={22} />
            </button>
          </div>
          {!c.bulk && c.counts.pending === 0 && (
            <div className="queue-summary">
              {c.counts.drafted} drafted · {c.counts.escalated} escalated
              <button type="button" className="link" onClick={c.resetQueue}>Reset</button>
            </div>
          )}
        </div>

        <div className="nav-label">Sample tickets</div>
        {c.samples.map((s) => (
          <button
            type="button"
            key={s.id}
            className={`nav-item ${c.activeSample === s.id ? 'active' : ''}`}
            onClick={() => c.loadSample(s)}
            disabled={c.bulk}
          >
            <span>{s.label}</span>
            {STATUS_TAG[c.queue[s.id]] && <span className="tag">{STATUS_TAG[c.queue[s.id]]}</span>}
          </button>
        ))}
      </nav>

      <div className="db-source" title="Cloud Storage bucket where analyzed tickets are stored">
        {storage.bucket ? <span>DB at <code>{storage.bucket}</code></span> : <span>{storage.text}</span>}
      </div>

      <div className="role">
        <div className="role-text">
          <div className="role-title">{OPERATOR.name}</div>
          <div className="role-sub">{OPERATOR.role}</div>
        </div>
        <Icon name="selector" size={16} />
      </div>
    </aside>
  )
}
