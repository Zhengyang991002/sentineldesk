import Icon from './Icon.jsx'

// Pale-blue strip under the topbar listing the Google Cloud services the backend is connected to.
// Read from GET /health; hidden until at least one service is configured.
export default function ServiceBand({ health }) {
  if (!health) return null
  const services = []
  if (health.gemini?.configured) services.push({ name: 'Vertex AI', detail: health.gemini.model })
  if (health.storage?.configured) services.push({ name: 'Cloud Storage', detail: health.storage.bucket })
  if (health.clients?.configured) services.push({ name: 'BigQuery', detail: health.clients.dataset })
  if (services.length === 0) return null

  return (
    <div className="band" role="status" aria-label="Connected Google Cloud services">
      <span className="band-label">Connected to Google Cloud</span>
      {services.map((s) => (
        <span className="band-item" key={s.name}>
          <Icon name="check" size={14} strokeWidth={2.2} />
          {s.name}
          <span className="band-detail">{s.detail}</span>
        </span>
      ))}
    </div>
  )
}
