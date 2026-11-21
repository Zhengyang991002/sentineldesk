// Helpers for the pseudonymous client attached to a ticket. A client is only ever shown as its
// "cust_…" id (a keyed hash); the email / account number / phone behind it is never stored.

export const KIND_LABEL = { email: 'Email', account: 'Account no.', phone: 'Phone' }

/** "cust_7db48f461f9b5a4b974fb57a" -> "cust_7db4…b57a" */
export const shortId = (id) => (id && id.length > 16 ? `${id.slice(0, 9)}…${id.slice(-4)}` : id || '')

/**
 * Normalizes a GET /tickets row's result so `result.client` is always present: new tickets carry it
 * inside `result`, older ones only have the top-level `client_id` of the stored record.
 * @returns {import('./api/client.js').TriageResult}
 */
export function resultWithClient(row) {
  const result = row.result
  if (result.client !== undefined) return result
  return { ...result, client: row.client_id ? { client_id: row.client_id, id_kind: null } : null }
}
