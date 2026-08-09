/**
 * Zone list — shows configured zones with delete button.
 * Highlights zones that have an active crossing alert.
 */
export default function ZoneList({ zones, activeAlertZoneIds, onDelete, loading }) {
  if (loading) {
    return (
      <div className="panel-body">
        <div className="empty-state">
          <div className="spinner" />
        </div>
      </div>
    )
  }

  if (zones.length === 0) {
    return (
      <div className="panel-body">
        <div className="empty-state">
          <span className="empty-icon">⬡</span>
          <p className="empty-text">No zones configured.<br />Draw one on the feed above.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="panel-body">
      {zones.map(zone => (
        <div
          key={zone.id}
          className={`zone-item ${activeAlertZoneIds.has(zone.id) ? 'active-alert' : ''}`}
        >
          <div className="flex flex-col gap-1" style={{ flex: 1, minWidth: 0 }}>
            <span className="zone-name truncate">{zone.name}</span>
            <div className="flex gap-2 items-center">
              <span className={`badge badge-${zone.zone_type}`}>
                {zone.zone_type === 'polygon' ? '⬡ Polygon' : '∕ Line'}
              </span>
              <span className="text-xs text-muted text-mono">
                {zone.points.length} pts
              </span>
              {activeAlertZoneIds.has(zone.id) && (
                <span className="text-xs text-alert" style={{ fontWeight: 600 }}>
                  ● ALERT
                </span>
              )}
            </div>
          </div>
          <button
            id={`btn-delete-zone-${zone.id}`}
            className="btn btn-danger btn-icon"
            onClick={() => onDelete(zone.id)}
            title="Delete zone"
            aria-label={`Delete zone ${zone.name}`}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
