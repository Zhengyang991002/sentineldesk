import { useEffect, useState } from 'react'
import { STORAGE_KEYS } from './config.js'
import useConsole from './hooks/useConsole.js'
import useAssignment from './hooks/useAssignment.js'
import useStoredState from './hooks/useStoredState.js'
import Answers from './components/Answers.jsx'
import ChatWidget from './components/ChatWidget.jsx'
import Clients from './components/Clients.jsx'
import Managers from './components/Managers.jsx'
import Models from './components/Models.jsx'
import HistoryMenu from './components/HistoryMenu.jsx'
import OutageBanner from './components/OutageBanner.jsx'
import Progress from './components/Progress.jsx'
import Result from './components/Result.jsx'
import Sidebar from './components/Sidebar.jsx'
import TicketForm from './components/TicketForm.jsx'
import ServiceBand from './components/ServiceBand.jsx'
import Topbar from './components/Topbar.jsx'
import jerry from '../assets/Jerry.png'
import leo from '../assets/Leo.jpeg'
import miguel from '../assets/Miguel.png'
import rorry from '../assets/Rorry.png'
import sofia from '../assets/Sofia.png'

const TEAM = [
  { name: 'Jerry', photo: jerry },
  { name: 'Leo', photo: leo },
  { name: 'Miguel', photo: miguel },
  { name: 'Rorry', photo: rorry },
  { name: 'Sofia', photo: sofia },
]

// Layout only. State and actions live in hooks/useConsole.js, backend calls in api/client.js.
export default function App() {
  const c = useConsole()
  const assignment = useAssignment(c.status === 'done' ? c.result : null)
  const [collapsed, setCollapsed] = useStoredState(STORAGE_KEYS.sidebarCollapsed, false)

  const [page, setPage] = useStoredState(STORAGE_KEYS.page, 'triage')
  const [clientFocus, setClientFocus] = useState('') // client id to pre-filter the Clients page with
  const navigate = (p) => {
    setClientFocus('')
    setPage(p)
  }
  const openClient = (id) => {
    setClientFocus(id)
    setPage('clients')
  }

  // New ticket as if it came from this client: blank form, client preselected.
  const ticketFor = (client) => {
    c.clear()
    c.setClientId(client.client_id)
    setClientFocus('')
    setPage('triage')
  }
  useEffect(() => {
    if (page === 'triage') c.reloadClients()
  }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

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
      <Topbar
        console={c}
        page={page}
        onOpenTicket={(t) => {
          setPage('triage')
          c.openPast(t)
        }}
      />
      <OutageBanner burst={c.burst} />
      <ServiceBand health={c.health} />
      <div className={`shell ${collapsed ? 'collapsed' : ''}`}>
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed(!collapsed)}
          console={c}
          page={page}
          onNavigate={navigate}
        />

        {page === 'clients' ? (
          <Clients focus={clientFocus} onNewTicket={ticketFor} />
        ) : page === 'managers' ? (
          <Managers />
        ) : page === 'models' ? (
          <Models />
        ) : (
        <main className="work">
          <section className="input-col" aria-label="Ticket input">
            <div className="stack-top">
              <button
                type="button"
                className="history-btn"
                onClick={c.clear}
                disabled={c.bulk || (!hasTicket && c.status === 'idle')}
                title="Close the current ticket and start blank"
              >
                Clear
              </button>
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
                clients={c.clientList}
                clientId={c.clientId}
                onClient={c.setClientId}
                onSubmit={c.analyze}
              />
              <Answers status={c.status} result={c.result} assignment={assignment} onCitationClick={c.jumpToPrecedent} />
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
              {c.status === 'done' && c.result && <Result result={c.result} precedents={precedents} onOpenClient={openClient} assignment={assignment} />}
            </section>
          </div>
        </main>
        )}
      </div>

      <footer className="footer">
        <div className="credits">
          <span className="credits-label">Developed By</span>
          <ul className="team" aria-label="Team">
            {TEAM.map((m) => (
              <li key={m.name} title={m.name}>
                <img src={m.photo} alt={m.name} />
              </li>
            ))}
          </ul>
        </div>
      </footer>

      <ChatWidget
        result={c.status === 'done' ? c.result : null}
        current={hasTicket ? { subject: c.subject.trim(), body: c.body.trim() } : null}
      />
    </div>
  )
}
