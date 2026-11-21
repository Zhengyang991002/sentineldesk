import { useState } from 'react'
import { KIND_LABEL, shortId } from '../clientId.js'
import { ON_CALL } from '../mocks/onCall.js'

const pct = (x) => `${Math.round(x * 100)}%`
const PRECEDENT_PREVIEW_CHARS = 240

// Right-hand panel for a finished analysis: gate decision, classification, latency, precedents.
// `precedents` carries the list controls owned by useConsole (filters, highlight, scroll refs).
export default function Result({ result, precedents, onOpenClient, assignment }) {
  const { escalation } = result
  const { query, setQuery, minSim, setMinSim, highlight, refs } = precedents
  const needle = query.trim().toLowerCase()
  const shown = result.retrieved.filter(
    (r) =>
      r.score >= minSim &&
      (!needle || r.ticket_id.toLowerCase().includes(needle) || r.answer.toLowerCase().includes(needle)),
  )

  return (
    <>
      <div className={`statusbar ${escalation.escalate ? 'bad' : 'good'}`} role="status">
        <span className="statusbar-text">
          <span className="statusbar-title">
            <span aria-hidden="true">{escalation.escalate ? '▲' : '✓'}</span>{' '}
            {escalation.escalate ? 'Escalate to Supervisor' : 'Auto-Draft Ready'}
          </span>
          <span className="statusbar-reason">
            {escalation.reason}
            {escalation.decided_by && (
              <span className="muted"> · decided by {{ agent: "Gemini agent", ml: "ML model", rule: "no-precedent rule (agent unavailable)" }[escalation.decided_by] || escalation.decided_by}</span>
            )}
          </span>
        </span>
        {escalation.escalate && (
          <span className="managers" role="group" aria-label="Human input required: on-call managers" title="Human input required">
            {ON_CALL.map((person) => (
              <span
                className={`manager ${assignment.data?.manager_id === person.id ? 'picked' : ''}`}
                key={person.id}
                title={person.name}
              >
                <img
                  src={person.photo}
                  alt={person.name}
                  style={{ objectPosition: person.position, transformOrigin: person.origin }}
                />
              </span>
            ))}
          </span>
        )}
      </div>

      {!escalation.escalate && escalation.flag_reasons?.length > 0 && (
        <ul className="flags" aria-label="Review before sending">
          {escalation.flag_reasons.map((reason, i) => (
            <li key={i}>
              <span aria-hidden="true">⚠</span> {reason}
            </li>
          ))}
        </ul>
      )}

      <div className="cards">
        <ConfidenceCard title="Type" label={result.type} confidence={result.confidences.type} />
        <ConfidenceCard title="Queue" label={result.queue} confidence={result.confidences.queue} />
        <ConfidenceCard
          title="Priority"
          label={result.priority.toUpperCase()}
          confidence={result.confidences.priority}
          tone={result.priority}
        />
      </div>

      <div className="meta">
        <span className="lang">
          Language: <Flag lang={result.language} /> <strong>{result.language.toUpperCase()}</strong>
        </span>
        {result.client && (
          <button
            type="button"
            className="client-chip"
            onClick={() => onOpenClient?.(result.client.client_id)}
            title={`${result.client.client_id}. Open this client`}
          >
            Client: <code>{shortId(result.client.client_id)}</code>
            {result.client.id_kind && <span className="client-kind"> · {KIND_LABEL[result.client.id_kind] || result.client.id_kind}</span>}
          </button>
        )}
        {result.client === null && <span className="muted">Client: not identified</span>}
        <span className="latency" tabIndex={0} aria-describedby="stage-tip">
          Latency: <strong>{result.latency_ms} ms</strong>
          <span id="stage-tip" role="tooltip" className="tip">
            {Object.entries(result.stage_ms).map(([stage, ms]) => (
              <span key={stage}>{stage}: {ms} ms</span>
            ))}
          </span>
        </span>
      </div>

      <div className="panel">
        <h2>Retrieved precedents</h2>
        <div className="filters">
          <input
            type="search"
            className="search"
            placeholder="Search precedents…"
            aria-label="Search precedents"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className="filter"
            aria-label="Minimum similarity"
            value={minSim}
            onChange={(e) => setMinSim(Number(e.target.value))}
          >
            <option value={0}>Any similarity</option>
            <option value={0.8}>≥ 0.80</option>
            <option value={0.7}>≥ 0.70</option>
            <option value={0.6}>≥ 0.60</option>
            <option value={0.5}>≥ 0.50</option>
          </select>
          <span className="muted count">{shown.length} of {result.retrieved.length}</span>
        </div>
        <ul className="precedents">
          {shown.map((r) => (
            <Precedent
              key={r.ticket_id}
              precedent={r}
              active={highlight === r.ticket_id}
              refCallback={(el) => (refs.current[r.ticket_id] = el)}
            />
          ))}
          {shown.length === 0 && <li className="muted">No precedents match the current filters.</li>}
        </ul>
      </div>
    </>
  )
}

function Precedent({ precedent, active, refCallback }) {
  const [expanded, setExpanded] = useState(false)
  const { answer } = precedent
  const truncated = answer.length > PRECEDENT_PREVIEW_CHARS
  const text = expanded || !truncated ? answer : answer.slice(0, PRECEDENT_PREVIEW_CHARS).trimEnd() + '…'

  return (
    <li ref={refCallback} className={`precedent ${active ? 'active' : ''}`}>
      <div className="p-head">
        <code>{precedent.ticket_id}</code>
        {precedent.language && <span className="muted">{precedent.language.toUpperCase()}</span>}
        <span className="score">sim {precedent.score.toFixed(2)}</span>
      </div>
      <p>{text}</p>
      {truncated && (
        <button type="button" className="link" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
          {expanded ? 'show less' : 'show more'}
        </button>
      )}
    </li>
  )
}

function ConfidenceCard({ title, label, confidence, tone }) {
  return (
    <div
      className={`card ${tone ? 'tone-' + tone : ''}`}
      role="meter"
      aria-label={`${title} confidence`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(confidence * 100)}
    >
      <div className="card-title">{title}</div>
      <div className="card-body">
        <Knob value={confidence} />
        <div className="card-text">
          <div className="card-label">{label}</div>
          <div className="card-conf">{pct(confidence)} confidence</div>
        </div>
      </div>
    </div>
  )
}

// Dial sweeping 270 degrees, from -135 (value 0) to +135 (value 1).
const polar = (cx, cy, r, deg) => {
  const rad = (deg * Math.PI) / 180
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)]
}

function arcPath(cx, cy, r, from, to) {
  const [x1, y1] = polar(cx, cy, r, from)
  const [x2, y2] = polar(cx, cy, r, to)
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
}

function Knob({ value }) {
  const v = Math.min(1, Math.max(0, value))
  const start = 135
  const angle = start + 270 * v
  const [px, py] = polar(32, 32, 14, angle)
  const [qx, qy] = polar(32, 32, 7, angle)
  return (
    <svg className="knob" viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">
      <path d={arcPath(32, 32, 26, start, start + 270)} className="knob-track" />
      {v > 0 && <path d={arcPath(32, 32, 26, start, angle)} className="knob-value" />}
      <circle cx="32" cy="32" r="18" className="knob-body" />
      <line x1={qx} y1={qy} x2={px} y2={py} className="knob-pointer" />
    </svg>
  )
}

function Flag({ lang }) {
  if (lang === 'de') {
    return (
      <svg className="flag" viewBox="0 0 20 14" width="20" height="14" role="img" aria-label="Germany">
        <rect width="20" height="4.67" y="0" fill="#000" />
        <rect width="20" height="4.67" y="4.67" fill="#dd0000" />
        <rect width="20" height="4.67" y="9.33" fill="#ffce00" />
      </svg>
    )
  }
  const stripes = Array.from({ length: 7 }, (_, i) => i)
  const stars = []
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 4; col++) stars.push([1.6 + col * 1.9, 1.5 + row * 2.2])
  }
  return (
    <svg className="flag" viewBox="0 0 20 14" width="20" height="14" role="img" aria-label="United States">
      <rect width="20" height="14" fill="#fff" />
      {stripes.map((i) => (
        <rect key={i} width="20" height={14 / 13} y={(i * 2 * 14) / 13} fill="#b22234" />
      ))}
      <rect width="8.4" height={(7 * 14) / 13} fill="#3c3b6e" />
      {stars.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="0.5" fill="#fff" />
      ))}
    </svg>
  )
}
