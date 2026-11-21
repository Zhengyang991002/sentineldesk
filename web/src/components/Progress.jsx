import { useEffect, useState } from 'react'
import { PIPELINE_STEPS, STEP_MS } from '../config.js'

// MOCK: the active step is derived from elapsed time, not from backend events.
export default function Progress() {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const startedAt = performance.now()
    const id = setInterval(() => setElapsed(performance.now() - startedAt), 100)
    return () => clearInterval(id)
  }, [])

  const active = STEP_MS > 0 ? Math.min(PIPELINE_STEPS.length - 1, Math.floor(elapsed / STEP_MS)) : 0

  return (
    <div className="progress" role="status" aria-busy="true" aria-label="Analyzing ticket">
      <div className="progress-head">
        <h2>Analyzing ticket…</h2>
        <span className="progress-time">{(elapsed / 1000).toFixed(1)} s</span>
      </div>
      <ol className="steps">
        {PIPELINE_STEPS.map((step, i) => {
          const state = i < active ? 'done' : i === active ? 'running' : 'waiting'
          return (
            <li key={step.key} className={`step ${state}`}>
              <span className="step-mark" aria-hidden="true">{state === 'done' ? '✓' : ''}</span>
              <span className="step-body">
                <span className="step-label">{step.label}</span>
                <span className="step-hint">{step.hint}</span>
              </span>
              <span className="step-status">
                {state === 'done' ? 'Done' : state === 'running' ? 'Running…' : 'Waiting'}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
