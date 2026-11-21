import { useState } from 'react'
import geminiLogo from '../../assets/gemini_logo.webp'
import Icon from './Icon.jsx'

// "Sentinel Answers" card under the ticket form: the drafted reply and the precedents it cites.
export default function Answers({ status, result, onCitationClick }) {
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
              <p className="muted">No draft generated: ticket escalated</p>
            ))}
          <div className="powered">
            <span>Powered by</span>
            <img src={geminiLogo} alt="" width="14" height="14" />
            <span className="powered-name">Gemini</span>
          </div>
        </div>
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
