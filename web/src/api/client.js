// Every call to the backend goes through this file. Paths are proxied to the FastAPI app
// by vite.config.js in dev and preview. Response shapes are documented in docs/ARCHITECTURE.md.

/**
 * @typedef {Object} TriageResult
 * @property {string} type
 * @property {string} queue
 * @property {'high'|'medium'|'low'} priority
 * @property {{type: number, queue: number, priority: number}} confidences  0..1
 * @property {'en'|'de'} language
 * @property {number} latency_ms
 * @property {{triage: number, retrieve: number, gate: number, draft: number}} stage_ms
 * @property {{escalate: boolean, reason: string}} escalation
 * @property {{ticket_id: string, score: number, answer: string}[]} retrieved
 * @property {{reply: string, cited_ids: string[], source?: 'llm'|'fallback'}|null} draft  null when the ticket is escalated; source 'llm' = written by Gemini
 * @property {Burst|null} burst  outage state right after this ticket was added
 * @property {{client_id: string, id_kind: string|null}|null} client  pseudonymous client (keyed hash), null if the ticket has no identifier
 */

const UNREACHABLE = 'Could not reach the backend. Is uvicorn running on port 8000?'

function messageFor(status, body) {
  const detail = body && body.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return detail.map((e) => e.msg).join('; ')
  if (status >= 500) return `Backend unavailable (HTTP ${status}). Is uvicorn running on port 8000?`
  return `Request failed (HTTP ${status}).`
}

async function request(path, { method = 'GET', json, signal } = {}) {
  let res
  try {
    res = await fetch(path, {
      method,
      signal,
      headers: json ? { 'Content-Type': 'application/json' } : undefined,
      body: json ? JSON.stringify(json) : undefined,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error(UNREACHABLE)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(messageFor(res.status, body))
  return body
}

/** Backend status: retrieval backend and classifier in use, whether Gemini and Cloud Storage are configured. */
export const getHealth = (signal) => request('/health', { signal })

/** @returns {Promise<TriageResult>} */
export const triage = ({ subject, body, client }, signal) =>
  request('/triage', {
    method: 'POST',
    json: { subject: subject || null, body, client_id: client?.client_id || null, client_kind: client?.id_kind || null },
    signal,
  })

/** @returns {Promise<{reply: string, model: string}>} */
export const chat = ({ message, history, ticket }, signal) =>
  request('/chat', { method: 'POST', json: { message, history, ticket }, signal })

/** Past tickets saved in Cloud Storage, newest first. */
export const listTickets = (limit, signal) => request(`/tickets?limit=${limit}`, { signal })

/**
 * Pseudonymous clients from the BigQuery `clients` view, most recently seen first.
 * `configured` is false when the backend has no BQ_DATASET / CLIENT_ID_SALT.
 * @returns {Promise<{configured: boolean, clients: Client[]}>}
 */
export const listClients = (limit, signal) => request(`/clients?limit=${limit}`, { signal })

/**
 * @typedef {Object} Client
 * @property {string} client_id       "cust_" + HMAC of the email / account number / phone; no personal data
 * @property {'email'|'account'|'phone'} id_kind
 * @property {string} first_seen      ISO timestamp
 * @property {string} last_seen       ISO timestamp
 * @property {number} ticket_count
 * @property {number} escalated_count
 * @property {string[]} languages
 * @property {string[]} queues
 */

/**
 * Register a client by email, account number or phone. The server hashes the value and never stores it.
 * `created` is false when that client already exists.
 * @param {{kind: 'email'|'account'|'phone', value: string}} client
 * @returns {Promise<{client_id: string, id_kind: string, created: boolean}>}
 */
export const addClient = ({ kind, value }, signal) => request('/clients', { method: 'POST', json: { kind, value }, signal })

/**
 * Manager assignment agent: which manager should take an escalated ticket.
 * `source` is 'gemini' when the agent decided, 'rules' when the deterministic fallback did.
 * @param {TriageResult} ticket
 * @returns {Promise<{manager_id: string, name: string, role: string, reason: string, source: 'gemini'|'rules'}>}
 */
export const assignManager = (ticket, signal) => request('/assign-manager', { method: 'POST', json: { ticket }, signal })

/**
 * @typedef {Object} Burst
 * @property {boolean} outage       true when several recent tickets describe the same failure
 * @property {number} size
 * @property {string} label         failing system, e.g. "VPN"
 * @property {number|null} since    epoch seconds of the oldest ticket in the cluster
 * @property {number} window_s
 * @property {{subject: string, language: string, at: number}[]} members  masked, newest first
 */

/** Current outage cluster among recent tickets. @returns {Promise<Burst>} */
export const getBurst = (signal) => request('/burst', { signal })
