import { STORAGE_KEYS } from './config.js'
import useConsole from './hooks/useConsole.js'
import useStoredState from './hooks/useStoredState.js'
import Answers from './components/Answers.jsx'
import ChatWidget from './components/ChatWidget.jsx'
import HistoryMenu from './components/HistoryMenu.jsx'
import Progress from './components/Progress.jsx'
import Result from './components/Result.jsx'
import Sidebar from './components/Sidebar.jsx'
import TicketForm from './components/TicketForm.jsx'
import Topbar from './components/Topbar.jsx'

// Layout only. State and actions live in hooks/useConsole.js, backend calls in api/client.js.
export default function App() {
  const c = useConsole()
  const [collapsed, setCollapsed] = useStoredState(STORAGE_KEYS.sidebarCollapsed, false)

  const hasTicket = c.body.trim() || c.subject.trim()
  const precedents = {
    query: c.query,
    setQuery: c.setQuery,
    minSim: c.minSim,
    setMinSim: c.setMinSim,
    highlight: c.highlight,
    refs: c.precedentRefs,
  }

  return (
    <div className="app">
      <Topbar />
      <div className={`shell ${collapsed ? 'collapsed' : ''}`}>
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} console={c} />

        <main className="work">
          <section className="input-col" aria-label="Ticket input">
            <div className="stack-top">
              <HistoryMenu
                localItems={c.history.items}
                onClearLocal={c.history.clear}
                onOpen={c.openPast}
                disabled={c.bulk}
                storageEnabled={c.storageEnabled}
              />
            </div>
            <div className="stack">
              <TicketForm
                subject={c.subject}
                onSubject={c.setSubject}
                body={c.body}
                onBody={c.setBody}
                canSubmit={c.canSubmit}
                loading={c.status === 'loading'}
                onSubmit={c.analyze}
              />
              <Answers status={c.status} result={c.result} onCitationClick={c.jumpToPrecedent} />
            </div>
          </section>

          <div className="results-col">
            <section className="results" aria-label="Triage result" aria-live="polite">
              {c.status === 'idle' && (
                <div className="empty">
                  <h2>No ticket analyzed yet</h2>
                  <p className="muted">Enter a ticket or load a sample, then press “Analyze ticket”.</p>
                </div>
              )}
              {c.status === 'loading' && <Progress />}
              {c.status === 'error' && (
                <div className="panel error" role="alert">
                  <strong>Error:</strong> {c.error}
                </div>
              )}
              {c.status === 'done' && c.result && <Result result={c.result} precedents={precedents} />}
            </section>
          </div>
        </main>
      </div>

      <footer className="footer" />

      <ChatWidget
        result={c.status === 'done' ? c.result : null}
        current={hasTicket ? { subject: c.subject.trim(), body: c.body.trim() } : null}
      />
    </div>
  )
}
