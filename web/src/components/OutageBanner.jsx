import { useState } from 'react'

const time = (epoch) => new Date(epoch * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

// Red strip under the topbar when several recent tickets describe the same failure (GET /burst, or the
// `burst` field of a triage result). Subjects shown are already PII-masked by the backend.
// Dismissing hides it until the cluster grows or a different system fails.
export default function OutageBanner({ burst }) {
  const [dismissed, setDismissed] = useState('')
  if (!burst || !burst.outage) return null
  const signature = `${burst.label}:${burst.size}`
  if (dismissed === signature) return null
  const langs = [...new Set(burst.members.map((m) => m.language.toUpperCase()).filter(Boolean))].join(' + ')
  const minutes = Math.max(1, Math.round((Date.now() / 1000 - burst.since) / 60))

  return (
    <div className="outage" role="alert">
      <div className="outage-main">
        <strong className="outage-title">▲ Major incident: possible {burst.label} outage</strong>
        <span>
          {burst.size} tickets in the last {minutes} min describe the same failure
          {langs ? ` (${langs})` : ''}. First reported at {time(burst.since)}.
        </span>
        <ul className="outage-members" aria-label="Tickets in this incident">
          {burst.members.slice(0, 5).map((m, i) => (
            <li key={i}>{m.subject}</li>
          ))}
        </ul>
      </div>
      <button type="button" className="outage-dismiss" onClick={() => setDismissed(signature)} aria-label="Dismiss outage banner">
        Dismiss
      </button>
    </div>
  )
}
