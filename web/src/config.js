// Frontend constants. Anything marked MOCK is a stand-in for data or behaviour
// that should eventually come from the backend (see docs/ARCHITECTURE.md).

export const REPO_URL = 'https://github.com/Zhengyang991002/sentineldesk'

export const STORAGE_KEYS = {
  history: 'sentineldesk.history',
  sidebarCollapsed: 'sentineldesk.sidebar.collapsed',
  page: 'sentineldesk.page',
}

export const LOCAL_HISTORY_MAX = 20
export const REMOTE_HISTORY_LIMIT = 30
export const CLIENTS_LIMIT = 50
export const BURST_POLL_MS = 15000

// Stages shown in the progress stepper, in pipeline order. Keys match `stage_ms` in the /triage response.
export const PIPELINE_STEPS = [
  { key: 'triage', label: 'Triage', hint: 'Classifying type, queue and priority' },
  { key: 'retrieve', label: 'Retrieve', hint: 'Finding similar past tickets' },
  { key: 'gate', label: 'Gate', hint: 'Deciding auto-draft vs. escalation' },
  { key: 'draft', label: 'Draft', hint: 'Writing the reply with citations' },
]

// MOCK: the stepper advances on a timer, it is not driven by the backend. Each step is shown for
// STEP_MS and the result is held back until every step has played. Set STEP_MS to 0 to show
// results as soon as the response arrives, or replace the timer with real stage events.
export const STEP_MS = 1000
export const MIN_ANALYSIS_MS = PIPELINE_STEPS.length * STEP_MS

// Pause between tickets when running "Answer all".
export const BULK_PAUSE_MS = 800

// MOCK: there is no auth yet; this is the operator shown in the sidebar.
export const OPERATOR = { name: 'IT Administrator', role: 'Operator role' }
