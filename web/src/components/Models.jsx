import { useState } from 'react'

// Models page, two views:
//   "Deployed model": parameters and evaluation of the classifier the API serves (Sentinel v2).
//   "Comparison": previous ML models evaluated for triage. Metrics are rows, models are columns.
// MOCK: static numbers copied from artifacts/sentinel_model/model.joblib, reports/train_sentinel_v2.log and
// reports/eval_by_language.md, not served by the backend yet. Update them when the model is retrained.

const VIEWS = [
  { key: 'deployed', label: 'Deployed model' },
  { key: 'comparison', label: 'Comparison' },
]

// ---------------------------------------------------------------- Deployed model (Sentinel v2)

const DEPLOYED = {
  name: 'Sentinel v2',
  trained: 'Nov 21, 13:38 · 1087 s on CPU',
  path: 'artifacts/sentinel_model/',
  note:
    'Validation split of the model (2,317 tickets, 10% of the 80% KB; kNN index = train part only). ' +
    'Ensemble weights and temperatures were tuned on this same split, so these numbers are slightly optimistic. ' +
    'The 20% test split was never loaded during training; v2 has not been scored on it yet.',
}

const SUMMARY = [
  { label: 'Type', f1: 0.930, acc: 0.930 },
  { label: 'Queue', f1: 0.794, acc: 0.798 },
  { label: 'Priority', f1: 0.833, acc: 0.837 },
]

const KPIS = [
  { label: 'High-priority Incident recall', value: '0.905' },
  { label: 'Severity threshold (HPI)', value: '0.264' },
  { label: 'Median top-1 similarity', value: '0.935' },
  { label: 'Classes', value: '4 · 10 · 3' },
]

const LEARNED = [
  { label: 'Type', lr: 0.1, char: 0.4, emb: 0.5, temp: 0.530 },
  { label: 'Queue', lr: 0.2, char: 0.3, emb: 0.5, temp: 0.644 },
  { label: 'Priority', lr: 0.0, char: 0.4, emb: 0.6, temp: 0.594 },
]

const HYPERPARAMS = [
  ['Word TF-IDF', '1-2 grams, min_df=2, sublinear_tf, 200k features'],
  ['Char TF-IDF', 'char_wb 3-5 grams, min_df=3, sublinear_tf, 200k features'],
  ['Logistic regression', 'one per label, C=4, class_weight="balanced", max_iter=2000'],
  ['kNN votes', 'k=10 · sources: char TF-IDF cosine + multilingual MiniLM embeddings (384-d) · softmax τ=0.05, smoothing 0.02'],
  ['Ensemble', 'weighted average of LR + kNN char + kNN emb, weights picked by val macro-F1 (0.1 grid)'],
  ['Calibration', 'temperature scaling per label (fit on val)'],
  ['Severity gate (R1)', 'P(Incident) × P(high) ≥ 0.264, tuned on val for recall ≥ 0.90'],
  ['Data', '80% KB = 22,869 tickets: 90% train / 10% val (seed 42) · 20% test never loaded'],
  ['Runtime', 'scikit-learn 1.9.1 · fastembed (ONNX) · ~4 ms per ticket for triage'],
]

const BY_LANGUAGE = [
  { label: 'Tickets', en: 1328, de: 989, all: 2317, int: true },
  { label: 'Type accuracy', en: 0.947, de: 0.907, all: 0.930 },
  { label: 'Queue accuracy', en: 0.850, de: 0.727, all: 0.798 },
  { label: 'Priority accuracy', en: 0.884, de: 0.774, all: 0.837 },
  { label: 'HP-Incident recall', en: 0.917, de: 0.888, all: 0.905 },
  { label: 'Language detection', en: 1.0, de: 0.753, all: 0.895 },
]

const ABLATION = [
  { label: 'Type', lr: 0.851, char: 0.915, emb: 0.908, ens: 0.930 },
  { label: 'Queue', lr: 0.567, char: 0.746, emb: 0.740, ens: 0.798 },
  { label: 'Priority', lr: 0.625, char: 0.785, emb: 0.795, ens: 0.837 },
]

const WEAK_SPOTS = [
  { label: 'Type: Problem', de: 0.701, en: 0.839 },
  { label: 'Queue: Sales and Pre-Sales', de: 0.483, en: 0.765 },
  { label: 'Queue: Returns and Exchanges', de: 0.525, en: 0.833 },
  { label: 'Queue: General Inquiry', de: 0.562, en: 0.714 },
  { label: 'Queue: Human Resources', de: 0.571, en: 0.812 },
  { label: 'Queue: IT Support', de: 0.595, en: 0.787 },
]

const f3 = (v) => v.toFixed(3)

function Table({ head, rows, caption }) {
  return (
    <div className="model-block">
      {caption && <h3 className="model-h">{caption}</h3>}
      <div className="table-wrap">
        <table className="clients-table">
          <thead>
            <tr>
              {head.map((h, i) => (
                <th key={h} scope="col" className={i ? 'num' : undefined}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
  )
}

function DeployedModel() {
  return (
    <>
      <p className="clients-note">
        <strong>{DEPLOYED.name}</strong> · trained {DEPLOYED.trained} · <code>{DEPLOYED.path}</code>
        <br />
        {DEPLOYED.note}
      </p>

      <div className="model-kpis">
        {SUMMARY.map((s) => (
          <div className="model-kpi" key={s.label}>
            <div className="model-kpi-label">{s.label} macro-F1</div>
            <div className="model-kpi-value">{f3(s.f1)}</div>
            <div className="muted">accuracy {f3(s.acc)}</div>
          </div>
        ))}
        {KPIS.map((k) => (
          <div className="model-kpi" key={k.label}>
            <div className="model-kpi-label">{k.label}</div>
            <div className="model-kpi-value">{k.value}</div>
          </div>
        ))}
      </div>

      <Table
        caption="Accuracy by language (validation)"
        head={['Metric', 'EN', 'DE', 'All']}
        rows={BY_LANGUAGE.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            {['en', 'de', 'all'].map((k) => (
              <td key={k} className="num">{r.int ? r[k].toLocaleString() : f3(r[k])}</td>
            ))}
          </tr>
        ))}
      />

      <Table
        caption="Ablation: accuracy of each component alone vs. the ensemble"
        head={['Label', 'LR only', 'kNN char', 'kNN emb', 'Ensemble']}
        rows={ABLATION.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            <td className="num">{f3(r.lr)}</td>
            <td className="num">{f3(r.char)}</td>
            <td className="num">{f3(r.emb)}</td>
            <td className="num"><strong>{f3(r.ens)}</strong></td>
          </tr>
        ))}
      />

      <Table
        caption="Learned ensemble weights and temperatures"
        head={['Label', 'LR', 'kNN char', 'kNN emb', 'Temperature']}
        rows={LEARNED.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            <td className="num">{r.lr.toFixed(1)}</td>
            <td className="num">{r.char.toFixed(1)}</td>
            <td className="num">{r.emb.toFixed(1)}</td>
            <td className="num">{f3(r.temp)}</td>
          </tr>
        ))}
      />

      <Table
        caption="Weak spots (accuracy by language)"
        head={['Class', 'DE', 'EN']}
        rows={WEAK_SPOTS.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            <td className="num">{f3(r.de)}</td>
            <td className="num">{f3(r.en)}</td>
          </tr>
        ))}
      />

      <div className="model-block">
        <h3 className="model-h">Architecture and hyperparameters</h3>
        <div className="table-wrap">
          <table className="clients-table">
            <tbody>
              {HYPERPARAMS.map(([k, v]) => (
                <tr key={k}>
                  <th scope="row">{k}</th>
                  <td>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

// ---------------------------------------------------------------- Comparison of previous models

const MODELS = ['Actual', 'LR + kNN char', 'LR + kNN emb', 'kNN char + kNN emb']

// `best` says which direction wins: 'max' for scores, 'min' for the escalation R2 (lower is better).
const METRICS = [
  { label: 'DE type', best: 'max', values: [0.851, 0.867, 0.882, 0.885] },
  { label: 'DE queue', best: 'max', values: [0.584, 0.608, 0.651, 0.689] },
  { label: 'DE priority', best: 'max', values: [0.632, 0.668, 0.715, 0.753] },
  { label: 'DE escalation R2', best: 'min', pct: true, values: [19.5, 15.8, 12.5, 11.0] },
  { label: 'EN queue', best: 'max', values: [0.809, 0.823, 0.792, 0.843] },
  { label: 'EN priority', best: 'max', values: [0.844, 0.851, 0.83, 0.877] },
  { label: 'EN escalation R2', best: 'min', pct: true, values: [6.8, 6.4, 5.5, 3.7] },
]

const fmt = (m, v) => (m.pct ? `${v.toFixed(1)}%` : v.toFixed(3))

function Comparison() {
  return (
    <>
      <p className="clients-note">Previous ML models evaluated for triage. Best value per metric in bold.</p>
      <div className="table-wrap">
        <table className="clients-table">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {MODELS.map((name) => (
                <th key={name} scope="col" className="num">{name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map((m) => {
              const best = m.best === 'min' ? Math.min(...m.values) : Math.max(...m.values)
              return (
                <tr key={m.label}>
                  <th scope="row">{m.label}</th>
                  {m.values.map((v, i) => (
                    <td key={MODELS[i]} className="num">
                      {v === best ? <strong>{fmt(m, v)}</strong> : fmt(m, v)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default function Models() {
  const [view, setView] = useState('deployed')
  return (
    <main className="work clients-page">
      <section className="clients" aria-label="Models">
        <div className="clients-head">
          <h2 className="clients-title">Models</h2>
        </div>
        <div className="model-tabs" role="tablist" aria-label="Models views">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              role="tab"
              aria-selected={view === v.key}
              className={`model-tab ${view === v.key ? 'active' : ''}`}
              onClick={() => setView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </div>
        {view === 'deployed' ? <DeployedModel /> : <Comparison />}
      </section>
    </main>
  )
}
