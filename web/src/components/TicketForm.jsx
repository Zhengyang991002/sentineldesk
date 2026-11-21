import { KIND_LABEL, shortId } from '../clientId.js'

export default function TicketForm({ subject, onSubject, body, onBody, clients = [], clientId = '', onClient, canSubmit, loading, onSubmit }) {
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
      <label htmlFor="client">Client <span className="muted">(optional)</span></label>
      <select id="client" value={clientId} onChange={(e) => onClient(e.target.value)}>
        <option value="">Detect from ticket</option>
        {clients.map((c) => (
          <option key={c.client_id} value={c.client_id} title={c.client_id}>
            {shortId(c.client_id)}
            {c.id_kind ? ` · ${KIND_LABEL[c.id_kind] || c.id_kind}` : ''}
          </option>
        ))}
      </select>
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
