export default function TicketForm({ subject, onSubject, body, onBody, canSubmit, loading, onSubmit }) {
  // Ctrl/Cmd+Enter submits from either field.
  const submitOnShortcut = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      onSubmit()
    }
  }

  return (
    <form
      className="card-main"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <h1>New ticket</h1>
      <p className="muted lead">Paste a support ticket to triage it, retrieve precedents and draft a reply.</p>
      <label htmlFor="subject">Subject <span className="muted">(optional)</span></label>
      <input
        id="subject"
        value={subject}
        onChange={(e) => onSubject(e.target.value)}
        onKeyDown={submitOnShortcut}
        autoComplete="off"
      />
      <label htmlFor="body">Body</label>
      <textarea
        id="body"
        rows={8}
        value={body}
        onChange={(e) => onBody(e.target.value)}
        onKeyDown={submitOnShortcut}
        required
      />
      <div className="row">
        <button type="submit" className="primary" disabled={!canSubmit}>
          {loading ? 'Analyzing…' : 'Analyze ticket'}
        </button>
        <span className="muted hint">Ctrl+Enter</span>
      </div>
    </form>
  )
}
