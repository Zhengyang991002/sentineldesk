import { useState } from 'react'
import geminiLogo from '../../assets/gemini_logo.webp'
import { ON_CALL } from '../mocks/onCall.js'
import Icon from './Icon.jsx'

// "Sentinel Answers" card under the ticket form: the drafted reply and the precedents it cites.
export default function Answers({ status, result, assignment, onCitationClick }) {
  return (
    <div className={`answers-wrap ${status !== 'idle' ? 'open' : ''}`} aria-live="polite">
      <div className="answers-inner">
        <div className="card-main answers">
          <h2>Sentinel Answers</h2>
          {status === 'loading' && (
            <div aria-busy="true" aria-label="Loading answer">
              <div className="skel line-skel" />
              <div className="skel line-skel short" />
            </div>
          )}
          {status === 'error' && <p className="muted">No answer available.</p>}
          {status === 'done' && result &&
            (result.draft ? (
              <Draft
                draft={result.draft}
                knownIds={result.retrieved.map((r) => r.ticket_id)}
                onCitationClick={onCitationClick}
              />
            ) : (
              <PassTo assignment={assignment} />
            ))}
          {status === 'done' && result?.draft &&
            (result.draft.source === 'llm' ? (
              <div className="powered">
                <span>Powered by</span>
                <img src={geminiLogo} alt="" width="14" height="14" />
                <span className="powered-name">Gemini</span>
              </div>
            ) : (
              <div className="powered">
                <span>Template reply: closest precedent quoted (Gemini unavailable)</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}

// Escalated ticket: no draft, the Gemini agent recommends which manager to pass it to.
function PassTo({ assignment }) {
  const { status, data } = assignment || { status: 'idle' }
  if (status === 'loading' || status === 'idle') return <p className="muted" role="status">Choosing a manager…</p>
  if (status === 'error' || !data) return <p className="muted">No draft generated: ticket escalated</p>
  const person = ON_CALL.find((p) => p.id === data.manager_id)
  return (
    <div className="pass-to">
      {person && (
        <span className="pass-photo">
          <img src={person.photo} alt={data.name} style={{ objectPosition: person.position, transformOrigin: person.origin }} />
        </span>
      )}
      <div className="pass-text">
        <span className="pass-label">Pass to</span>
        <strong className="pass-name">{data.name}</strong>
        <span className="muted">{data.role}</span>
        <p className="pass-reason">{data.reason}</p>
        <span className="pass-source">{data.source === 'gemini' ? 'Recommended by Gemini' : 'Rule-based recommendation'}</span>
      </div>
    </div>
  )
}

function Draft({ draft, knownIds, onCitationClick }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(draft.reply)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <>
      <pre className="draft">{draft.reply}</pre>
      <div className="row">
        <button
          type="button"
          className="icon-btn"
          onClick={copy}
          aria-label={copied ? 'Copied' : 'Copy reply'}
          title={copied ? 'Copied' : 'Copy reply'}
        >
          <Icon name={copied ? 'check' : 'copy'} />
        </button>
        {draft.cited_ids.length > 0 && <span className="muted">Cited:</span>}
        {draft.cited_ids.map((id) => (
          <button
            type="button"
            key={id}
            className="chip"
            disabled={!knownIds.includes(id)}
            onClick={() => onCitationClick(id)}
          >
            {id}
          </button>
        ))}
      </div>
    </>
  )
}
