import { snapshotUrl, clipUrl } from '../api'

/**
 * Event detail modal.
 *
 * Shows the snapshot image and inline video clip (if available), plus
 * a metadata grid with all event fields.
 *
 * Closes on overlay click or Escape key.
 */
export default function EventDetail({ event, onClose }) {
  if (!event) return null

  const ts = new Date(event.timestamp)

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose()
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Event detail"
      id="event-detail-modal"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      <div className="modal">
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: '1rem', marginBottom: 2 }}>🚨 {event.zone_name}</h2>
            <p className="text-xs text-muted text-mono">
              {ts.toLocaleString()} · Track #{event.track_id}
            </p>
          </div>
          <button
            id="btn-close-event-modal"
            className="btn btn-ghost btn-icon"
            onClick={onClose}
            aria-label="Close event detail"
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {/* Snapshot */}
          {event.has_snapshot ? (
            <img
              id={`event-snapshot-${event.id}`}
              className="modal-snapshot"
              src={snapshotUrl(event.id)}
              alt="Event snapshot"
            />
          ) : (
            <div style={{
              width: '100%',
              height: 180,
              background: 'var(--bg-base)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              fontSize: '2rem',
              border: '1px solid var(--border-subtle)',
            }}>
              📷
            </div>
          )}

          {/* Clip */}
          {event.has_clip && (
            <div>
              <p className="text-xs text-secondary" style={{ marginBottom: 8 }}>
                📹 Evidence clip (pre + post event)
              </p>
              <video
                id={`event-clip-${event.id}`}
                className="modal-clip"
                src={clipUrl(event.id)}
                controls
                autoPlay
                muted
                playsInline
              />
            </div>
          )}

          {/* Metadata grid */}
          <div className="modal-meta-grid">
            <div className="meta-cell">
              <div className="meta-label">Zone</div>
              <div className="meta-value">{event.zone_name}</div>
            </div>
            <div className="meta-cell">
              <div className="meta-label">Track ID</div>
              <div className="meta-value">#{event.track_id}</div>
            </div>
            <div className="meta-cell">
              <div className="meta-label">Timestamp</div>
              <div className="meta-value" style={{ fontSize: '0.75rem' }}>
                {ts.toLocaleString()}
              </div>
            </div>
            <div className="meta-cell">
              <div className="meta-label">Event ID</div>
              <div className="meta-value" style={{ fontSize: '0.65rem' }}>
                {event.id.slice(0, 8)}…
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
