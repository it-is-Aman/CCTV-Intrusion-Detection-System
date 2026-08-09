import type { Zone } from '../types'

/** Human-readable trigger labels */
const TRIGGER_LABELS: Record<string, { icon: string; label: string; color: string }> = {
  entry:  { icon: '→',  label: 'On entry',  color: 'var(--accent-500)' },
  exit:   { icon: '←',  label: 'On exit',   color: 'var(--warn-500)' },
  both:   { icon: '↔',  label: 'Both ways', color: 'var(--text-secondary)' },
  a_to_b: { icon: '→',  label: 'A → B',    color: 'var(--accent-500)' },
  b_to_a: { icon: '←',  label: 'B → A',    color: 'var(--warn-500)' },
}

interface ZoneListProps {
  zones: Zone[]
  activeAlertZoneIds: Set<string>
  onDelete: (id: string) => void
  loading: boolean
}

/**
 * Zone list — shows configured zones with delete button.
 * Highlights zones that have an active crossing alert.
 * Shows the configured trigger direction (entry/exit/both/a_to_b/b_to_a).
 */
export default function ZoneList({ zones, activeAlertZoneIds, onDelete, loading }: ZoneListProps) {
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
      {zones.map(zone => {
        const triggerMeta = TRIGGER_LABELS[zone.trigger] ?? {
          icon: '?', label: zone.trigger, color: 'var(--text-muted)',
        }
        return (
          <div
            key={zone.id}
            className={`zone-item ${activeAlertZoneIds.has(zone.id) ? 'active-alert' : ''}`}
          >
            <div className="flex flex-col gap-1" style={{ flex: 1, minWidth: 0 }}>
              <span className="zone-name truncate">{zone.name}</span>
              <div className="flex gap-2 items-center" style={{ flexWrap: 'wrap' }}>
                <span className={`badge badge-${zone.zone_type}`}>
                  {zone.zone_type === 'polygon' ? '⬡ Polygon' : '∕ Line'}
                </span>
                <span
                  className="text-xs text-mono"
                  style={{ color: triggerMeta.color, fontWeight: 600 }}
                  title={`Alert trigger: ${triggerMeta.label}`}
                >
                  {triggerMeta.icon} {triggerMeta.label}
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
        )
      })}
    </div>
  )
}
