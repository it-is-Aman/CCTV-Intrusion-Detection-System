import { useState, useCallback, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useZones } from './hooks/useZones'
import { useEvents } from './hooks/useEvents'
import { WS_URL } from './api'

import LiveFeed from './components/LiveFeed'
import ZoneEditor from './components/ZoneEditor'
import ZoneList from './components/ZoneList'
import AlertBanner from './components/AlertBanner'
import EventList from './components/EventList'
import EventDetail from './components/EventDetail'

export default function App() {
  // ── WebSocket ─────────────────────────────────────────────────────────────
  const { lastMessage, readyState } = useWebSocket(WS_URL)

  // ── Zones ─────────────────────────────────────────────────────────────────
  const { zones, loading: zonesLoading, create: createZone, remove: removeZone } = useZones()

  // ── Events ────────────────────────────────────────────────────────────────
  const { events, loading: eventsLoading, error: eventsError, onWsMessage } = useEvents()

  // ── Alerts (banner stack) ─────────────────────────────────────────────────
  const [alerts, setAlerts] = useState([])
  const [activeAlertZoneIds, setActiveAlertZoneIds] = useState(new Set())

  useEffect(() => {
    if (!lastMessage) return
    onWsMessage(lastMessage)

    if (lastMessage.type === 'crossing') {
      const event = lastMessage.event
      setAlerts(prev => [event, ...prev.slice(0, 4)])
      setActiveAlertZoneIds(prev => new Set([...prev, event.zone_id]))
      // Clear zone alert highlight after 5s
      setTimeout(() => {
        setActiveAlertZoneIds(prev => {
          const next = new Set(prev)
          next.delete(event.zone_id)
          return next
        })
      }, 5000)
    }
  }, [lastMessage, onWsMessage])

  const dismissAlert = useCallback((id) => {
    setAlerts(prev => prev.filter(a => a.id !== id))
  }, [])

  // ── Drawing state ─────────────────────────────────────────────────────────
  const [drawMode, setDrawMode] = useState(null)
  const [drawingPoints, setDrawingPoints] = useState([])

  const handleStartDraw = useCallback((mode) => {
    setDrawMode(mode)
    setDrawingPoints([])
  }, [])

  const handleCanvasClick = useCallback((x, y) => {
    if (!drawMode) return
    setDrawingPoints(prev => {
      const next = [...prev, [x, y]]
      // Auto-close line after 2 points
      if (drawMode === 'line' && next.length === 2) {
        return next
      }
      return next
    })
  }, [drawMode])

  const handleCanvasDblClick = useCallback((_x, _y) => {
    // Double-click closes polygon (points already adequate)
  }, [])

  const handleSaveZone = useCallback(async (name: string, trigger: string) => {
    await createZone({
      name,
      zone_type: drawMode!,
      points: drawingPoints as [number, number][],
      trigger,
    })
    setDrawMode(null)
    setDrawingPoints([])
  }, [createZone, drawMode, drawingPoints])

  const handleCancelDraw = useCallback(() => {
    setDrawMode(null)
    setDrawingPoints([])
  }, [])

  // ── Event detail modal ────────────────────────────────────────────────────
  const [selectedEvent, setSelectedEvent] = useState(null)

  // ── Status indicator ──────────────────────────────────────────────────────
  const dotClass =
    alerts.length > 0 ? 'alert' :
    readyState === 'open' ? 'live' : ''

  const statusText =
    readyState === 'open' ? 'Connected' :
    readyState === 'connecting' ? 'Connecting…' : 'Disconnected'

  return (
    <div className="app-layout">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-brand">
          <div className="topbar-logo" aria-hidden>🎯</div>
          <div>
            <div className="topbar-title">Intrusion Detection</div>
            <div className="topbar-subtitle">local · webcam · MVP</div>
          </div>
        </div>

        <div className="topbar-status">
          <div className={`status-dot ${dotClass}`} aria-hidden />
          <span>{statusText}</span>
          {zones.length > 0 && (
            <span className="text-muted" style={{ marginLeft: 8 }}>
              {zones.length} zone{zones.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="main-content">
        {/* ── Left: feed + drawing toolbar ── */}
        <div className="feed-panel">
          <LiveFeed
            zones={zones}
            onCanvasClick={handleCanvasClick}
            onCanvasDblClick={handleCanvasDblClick}
            drawingPoints={drawingPoints}
            isDrawing={drawMode !== null}
          />
          <ZoneEditor
            drawMode={drawMode}
            drawingPoints={drawingPoints}
            onStartDraw={handleStartDraw}
            onFinish={handleSaveZone}
            onCancel={handleCancelDraw}
          />
        </div>

        {/* ── Right sidebar ── */}
        <aside className="sidebar">
          {/* Zones panel */}
          <div className="sidebar-panel" style={{ maxHeight: '45%', minHeight: 0 }}>
            <div className="panel-header">
              <span className="panel-title">Zones</span>
              <span className="text-xs text-muted text-mono">{zones.length}</span>
            </div>
            <ZoneList
              zones={zones}
              activeAlertZoneIds={activeAlertZoneIds}
              onDelete={removeZone}
              loading={zonesLoading}
            />
          </div>

          {/* Events panel */}
          <div className="sidebar-panel flex-1" style={{ minHeight: 0 }}>
            <div className="panel-header">
              <span className="panel-title">Events</span>
              <span className="text-xs text-muted text-mono">{events.length}</span>
            </div>
            <EventList
              events={events}
              loading={eventsLoading}
              error={eventsError}
              onSelect={setSelectedEvent}
            />
          </div>
        </aside>
      </main>

      {/* ── Alert banners (fixed, top-right) ── */}
      <AlertBanner alerts={alerts} onDismiss={dismissAlert} />

      {/* ── Event detail modal ── */}
      {selectedEvent && (
        <EventDetail event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      )}
    </div>
  )
}
