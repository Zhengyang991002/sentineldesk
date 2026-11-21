import { OPERATOR } from '../config.js'
import Icon from './Icon.jsx'

const STATUS_TAG = {
  processing: '… Processing',
  drafted: '✓ Drafted',
  escalated: '▲ Escalated',
  error: '! Error',
}

export default function Sidebar({ collapsed, onToggle, console: c, page, onNavigate }) {
  const total = c.samples.length

  if (collapsed) {
    return (
      <aside className="sidebar collapsed" aria-label="Navigation">
        <button type="button" className="rail-btn sidebar-toggle" onClick={onToggle} aria-label="Expand sidebar" title="Expand sidebar">
          <Icon name="expand" />
        </button>
        <nav className="rail">
          <button
            type="button"
            className={`rail-btn ${page === 'triage' ? 'active' : ''}`}
            onClick={() => onNavigate('triage')}
            aria-current={page === 'triage' ? 'page' : undefined}
            aria-label="Triage console"
            title="Triage console"
          >
            <Icon name="home" strokeWidth={1.8} />
          </button>
          <button
            type="button"
            className={`rail-btn ${page === 'clients' ? 'active' : ''}`}
            onClick={() => onNavigate('clients')}
            aria-current={page === 'clients' ? 'page' : undefined}
            aria-label="Clients"
            title="Clients"
          >
            <Icon name="clients" strokeWidth={1.8} />
          </button>
          <button
            type="button"
            className={`rail-btn ${page === 'managers' ? 'active' : ''}`}
            onClick={() => onNavigate('managers')}
            aria-current={page === 'managers' ? 'page' : undefined}
            aria-label="Managers"
            title="Managers"
          >
            <Icon name="user" strokeWidth={1.8} />
          </button>
          <button
            type="button"
            className={`rail-btn ${page === 'models' ? 'active' : ''}`}
            onClick={() => onNavigate('models')}
            aria-current={page === 'models' ? 'page' : undefined}
            aria-label="Models"
            title="Models"
          >
            <Icon name="db" strokeWidth={1.8} />
          </button>
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
              onClick={() => { onNavigate('triage'); c.loadSample(s) }}
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
          <div className="rail-btn" title={`${OPERATOR.name} · ${OPERATOR.role}`}><Icon name="user" strokeWidth={1.8} /></div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="sidebar" aria-label="Navigation">
      <div className="brand">
        <button type="button" className="icon-btn brand-toggle sidebar-toggle" onClick={onToggle} aria-label="Collapse sidebar" title="Collapse sidebar">
          <Icon name="collapse" />
        </button>
      </div>

      <nav>
        <div className="nav-label">Main</div>
        <button
          type="button"
          className={`nav-item ${page === 'triage' ? 'active' : ''}`}
          aria-current={page === 'triage' ? 'page' : undefined}
          onClick={() => onNavigate('triage')}
        >
          Triage console
        </button>
        <button
          type="button"
          className={`nav-item ${page === 'clients' ? 'active' : ''}`}
          aria-current={page === 'clients' ? 'page' : undefined}
          onClick={() => onNavigate('clients')}
        >
          Clients
        </button>
        <button
          type="button"
          className={`nav-item ${page === 'managers' ? 'active' : ''}`}
          aria-current={page === 'managers' ? 'page' : undefined}
          onClick={() => onNavigate('managers')}
        >
          Managers
        </button>
        <button
          type="button"
          className={`nav-item ${page === 'models' ? 'active' : ''}`}
          aria-current={page === 'models' ? 'page' : undefined}
          onClick={() => onNavigate('models')}
        >
          Models
        </button>

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
            onClick={() => { onNavigate('triage'); c.loadSample(s) }}
            disabled={c.bulk}
          >
            <span>{s.label}</span>
            {STATUS_TAG[c.queue[s.id]] && <span className="tag">{STATUS_TAG[c.queue[s.id]]}</span>}
          </button>
        ))}
      </nav>

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
