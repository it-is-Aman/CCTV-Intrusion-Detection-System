import { useState, useCallback, useRef } from 'react'

/**
 * Zone drawing toolbar and form.
 *
 * Props:
 *   onStartDraw(mode)  — called when user picks polygon or line mode
 *   onAddPoint(x, y)   — called by LiveFeed canvas click
 *   onFinish(name)     — called when user saves the drawn zone
 *   onCancel()         — cancel current drawing
 *   drawMode           — current drawing mode ('polygon' | 'line' | null)
 *   drawingPoints      — accumulated points so far
 */
export default function ZoneEditor({
  onStartDraw,
  onFinish,
  onCancel,
  drawMode,
  drawingPoints,
}) {
  const [zoneName, setZoneName] = useState('')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef(null)

  const minPoints = drawMode === 'polygon' ? 3 : 2
  const canSave = drawingPoints.length >= minPoints && zoneName.trim().length > 0

  const handleSave = useCallback(async () => {
    if (!canSave) return
    setSaving(true)
    try {
      await onFinish(zoneName.trim())
      setZoneName('')
    } finally {
      setSaving(false)
    }
  }, [canSave, onFinish, zoneName])

  const handleCancel = useCallback(() => {
    setZoneName('')
    onCancel()
  }, [onCancel])

  if (drawMode === null) {
    return (
      <div className="draw-form">
        <p className="text-xs text-muted" style={{ textAlign: 'center', marginBottom: 4 }}>
          Add a zone to start detecting crossings
        </p>
        <div className="flex gap-2">
          <button
            id="btn-draw-polygon"
            className="btn btn-ghost w-full"
            onClick={() => onStartDraw('polygon')}
          >
            ⬡ Polygon zone
          </button>
          <button
            id="btn-draw-line"
            className="btn btn-ghost w-full"
            onClick={() => onStartDraw('line')}
          >
            ∕ Tripwire line
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="draw-form">
      <div className="flex items-center justify-between">
        <span className={`badge badge-${drawMode}`}>
          {drawMode === 'polygon' ? '⬡ Drawing polygon' : '∕ Drawing tripwire'}
        </span>
        <span className="text-xs text-muted text-mono">
          {drawingPoints.length} / {minPoints}+ pts
        </span>
      </div>

      <p className="draw-hint">
        {drawMode === 'polygon'
          ? 'Click to add vertices · Double-click or Save to close'
          : 'Click two points to define the tripwire line'}
      </p>

      <input
        ref={inputRef}
        id="zone-name-input"
        className="input"
        placeholder="Zone name (e.g. Front door)"
        value={zoneName}
        onChange={e => setZoneName(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && canSave) void handleSave() }}
        autoFocus
      />

      <div className="flex gap-2">
        <button
          id="btn-save-zone"
          className="btn btn-primary w-full"
          disabled={!canSave || saving}
          onClick={() => void handleSave()}
        >
          {saving ? <span className="spinner" /> : null}
          {saving ? 'Saving…' : 'Save zone'}
        </button>
        <button
          id="btn-cancel-zone"
          className="btn btn-ghost"
          onClick={handleCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
