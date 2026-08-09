import { snapshotUrl } from '../api'

/**
 * Scrollable event history list.
 *
 * Each row shows a thumbnail (or placeholder), zone name, timestamp, and
 * track ID.  Clicking an event fires onSelect for the detail modal.
 */
export default function EventList({ events, loading, error, onSelect }) {
  if (loading) {
    return (
      <div className="panel-body">
        <div className="empty-state"><div className="spinner" /></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel-body">
        <div className="empty-state">
          <span className="empty-icon">⚠</span>
          <p className="empty-text">{error}</p>
        </div>
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="panel-body">
        <div className="empty-state">
          <span className="empty-icon">📋</span>
          <p className="empty-text">No crossing events yet.<br />Events appear here in real time.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="panel-body">
      {events.map(event => (
        <EventRow key={event.id} event={event} onSelect={onSelect} />
      ))}
    </div>
  )
}

function EventRow({ event, onSelect }) {
  const ts = new Date(event.timestamp)
  const formattedDate = ts.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const formattedTime = ts.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div
      className="event-item"
      id={`event-row-${event.id}`}
      role="button"
      tabIndex={0}
      onClick={() => onSelect(event)}
      onKeyDown={e => { if (e.key === 'Enter') onSelect(event) }}
      aria-label={`Event: ${event.zone_name} at ${formattedTime}`}
    >
      {event.has_snapshot ? (
        <img
          className="event-thumb"
          src={snapshotUrl(event.id)}
          alt={`Snapshot for event ${event.id}`}
          loading="lazy"
        />
      ) : (
        <div className="event-thumb-placeholder" aria-hidden>📷</div>
      )}

      <div className="event-info">
        <div className="event-zone truncate">{event.zone_name}</div>
        <div className="event-ts">{formattedDate} · {formattedTime}</div>
        <div className="event-track">Track #{event.track_id}</div>
      </div>

      {event.has_clip && (
        <span style={{ fontSize: '0.8rem' }} title="Clip available">🎬</span>
      )}
    </div>
  )
}
