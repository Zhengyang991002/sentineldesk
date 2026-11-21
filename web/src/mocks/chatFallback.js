// MOCK: rule-based answers used by the chat widget when POST /chat fails (Gemini not
// configured or unreachable). It only reads the analyzed ticket, it never calls a model.

const pct = (x) => `${Math.round(x * 100)}%`

export function localReply(question, r) {
  if (!r) {
    return 'No ticket has been analyzed yet. Analyze one and I can explain the triage, the precedents and the escalation decision.'
  }
  const q = question.toLowerCase()
  if (/escalat|why|reason|gate|human|por qu|motivo/.test(q)) {
    return `${r.escalation.escalate ? 'Escalated' : 'Auto-draft'}: ${r.escalation.reason}`
  }
  if (/priorit|urgen/.test(q)) {
    return `Priority is ${r.priority.toUpperCase()} with ${pct(r.confidences.priority)} confidence.`
  }
  if (/precedent|similar|retriev|history|antecedent/.test(q)) {
    if (!r.retrieved.length) return 'No precedents were retrieved for this ticket.'
    const top = r.retrieved
      .slice(0, 3)
      .map((p) => `${p.ticket_id} (sim ${p.score.toFixed(2)})`)
      .join(', ')
    return `Top precedents: ${top}.`
  }
  if (/language|idioma|german|english|alem|ingl/.test(q)) {
    return `Detected language: ${r.language === 'de' ? 'German' : 'English'}.`
  }
  if (/latenc|slow|speed|time|tiempo|ms\b/.test(q)) {
    const s = r.stage_ms
    return `End-to-end ${r.latency_ms} ms (triage ${s.triage}, retrieve ${s.retrieve}, gate ${s.gate}, draft ${s.draft}).`
  }
  if (/draft|reply|answer|respuesta/.test(q)) {
    return r.draft
      ? `A draft reply was generated, citing ${r.draft.cited_ids.join(', ') || 'no tickets'}.`
      : 'No draft was generated because the ticket was escalated.'
  }
  const article = /^[aeiou]/i.test(r.type) ? 'an' : 'a'
  return `This ticket is ${article} ${r.type} for the ${r.queue} queue (priority ${r.priority}). Ask me about the priority, precedents, language, latency or why it was escalated.`
}
