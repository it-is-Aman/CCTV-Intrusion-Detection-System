import { useState, useEffect, useCallback } from 'react'

const AUTO_DISMISS_MS = 4000

/**
 * Alert banner container — stacks sliding alert banners on WS crossing events.
 *
 * Each alert auto-dismisses after AUTO_DISMISS_MS ms and plays a slide-in
 * / slide-out animation.  Multiple simultaneous alerts stack vertically.
 */
export default function AlertBanner({ alerts, onDismiss }) {
  return (
    <div className="alert-banner-container" role="region" aria-live="assertive" aria-label="Alert notifications">
      {alerts.map(alert => (
        <AlertItem key={alert.id} alert={alert} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

function AlertItem({ alert, onDismiss }) {
  const [exiting, setExiting] = useState(false)

  const dismiss = useCallback(() => {
    setExiting(true)
    setTimeout(() => onDismiss(alert.id), 220)
  }, [alert.id, onDismiss])

  useEffect(() => {
    const t = setTimeout(dismiss, AUTO_DISMISS_MS)
    return () => clearTimeout(t)
  }, [dismiss])

  const ts = new Date(alert.timestamp).toLocaleTimeString()

  return (
    <div
      className={`alert-banner${exiting ? ' exiting' : ''}`}
      role="alert"
      id={`alert-${alert.id}`}
    >
      <span className="alert-icon">🚨</span>
      <div className="alert-content" style={{ flex: 1 }}>
        <div className="alert-title">Zone crossed: {alert.zone_name}</div>
        <div className="alert-meta">
          Track #{alert.track_id} · {ts}
        </div>
      </div>
      <button
        className="btn btn-icon btn-ghost"
        onClick={dismiss}
        aria-label="Dismiss alert"
        style={{ alignSelf: 'flex-start', marginLeft: 4 }}
      >
        ✕
      </button>
    </div>
  )
}
