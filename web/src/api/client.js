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
 * @property {{reply: string, cited_ids: string[]}|null} draft  null when the ticket is escalated
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

/** Backend status: which pipeline stages are mocked, whether Gemini and Cloud Storage are configured. */
export const getHealth = (signal) => request('/health', { signal })

/** @returns {Promise<TriageResult>} */
export const triage = ({ subject, body }, signal) =>
  request('/triage', { method: 'POST', json: { subject: subject || null, body }, signal })

/** @returns {Promise<{reply: string, model: string}>} */
export const chat = ({ message, history, ticket }, signal) =>
  request('/chat', { method: 'POST', json: { message, history, ticket }, signal })

/** Past tickets saved in Cloud Storage, newest first. */
export const listTickets = (limit, signal) => request(`/tickets?limit=${limit}`, { signal })
