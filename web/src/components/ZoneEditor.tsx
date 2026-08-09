import { useState, useCallback, useRef } from 'react'
import type { DrawMode, PolygonTrigger, LineTrigger } from '../types'

interface ZoneEditorProps {
  onStartDraw: (mode: DrawMode) => void
  onFinish: (name: string, trigger: string) => Promise<void>
  onCancel: () => void
  drawMode: DrawMode
  drawingPoints: [number, number][]
}

// ── Labels & options ──────────────────────────────────────────────────────────

const POLYGON_TRIGGERS: { value: PolygonTrigger; label: string; icon: string; hint: string }[] = [
  {
    value: 'entry',
    label: 'On Entry',
    icon: '→',
    hint: 'Alert when a person walks INTO the zone',
  },
  {
    value: 'exit',
    label: 'On Exit',
    icon: '←',
    hint: 'Alert when a person walks OUT of the zone',
  },
]

const LINE_TRIGGERS: { value: LineTrigger; label: string; icon: string; hint: string }[] = [
  {
    value: 'both',
    label: 'Both ways',
    icon: '↔',
    hint: 'Alert when crossing in either direction',
  },
  {
    value: 'a_to_b',
    label: 'A → B',
    icon: '→',
    hint: 'Alert when crossing from the A side to the B side (left of line direction)',
  },
  {
    value: 'b_to_a',
    label: 'B → A',
    icon: '←',
    hint: 'Alert when crossing from the B side to the A side (right of line direction)',
  },
]

// ── Component ─────────────────────────────────────────────────────────────────

export default function ZoneEditor({
  onStartDraw,
  onFinish,
  onCancel,
  drawMode,
  drawingPoints,
}: ZoneEditorProps) {
  const [zoneName, setZoneName] = useState('')
  const [polygonTrigger, setPolygonTrigger] = useState<PolygonTrigger>('entry')
  const [lineTrigger, setLineTrigger] = useState<LineTrigger>('both')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const minPoints = drawMode === 'polygon' ? 3 : 2
  const canSave = drawingPoints.length >= minPoints && zoneName.trim().length > 0

  const handleSave = useCallback(async () => {
    if (!canSave) return
    setSaving(true)
    try {
      const trigger = drawMode === 'polygon' ? polygonTrigger : lineTrigger
      await onFinish(zoneName.trim(), trigger)
      setZoneName('')
      setPolygonTrigger('entry')
      setLineTrigger('both')
    } finally {
      setSaving(false)
    }
  }, [canSave, onFinish, zoneName, drawMode, polygonTrigger, lineTrigger])

  const handleCancel = useCallback(() => {
    setZoneName('')
    setPolygonTrigger('entry')
    setLineTrigger('both')
    onCancel()
  }, [onCancel])

  // ── Idle state: mode picker ───────────────────────────────────────────────
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

  // ── Drawing state: show point count, trigger picker, name, save/cancel ────
  const triggerOptions = drawMode === 'polygon' ? POLYGON_TRIGGERS : LINE_TRIGGERS
  const currentTrigger = drawMode === 'polygon' ? polygonTrigger : lineTrigger
  const activeTriggerMeta = triggerOptions.find(t => t.value === currentTrigger)!

  return (
    <div className="draw-form">
      {/* Header */}
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

      {/* ── Trigger direction picker ── */}
      <div>
        <p className="text-xs text-muted" style={{ marginBottom: 6 }}>
          {drawMode === 'polygon' ? 'When to alert?' : 'Which crossing direction?'}
        </p>
        <div className="flex gap-2">
          {triggerOptions.map(opt => (
            <button
              key={opt.value}
              id={`btn-trigger-${opt.value}`}
              className={`btn w-full ${currentTrigger === opt.value ? 'btn-active' : 'btn-ghost'}`}
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={() => {
                if (drawMode === 'polygon') setPolygonTrigger(opt.value as PolygonTrigger)
                else setLineTrigger(opt.value as LineTrigger)
              }}
              title={opt.hint}
              aria-pressed={currentTrigger === opt.value}
            >
              <span style={{ fontSize: '0.9rem' }}>{opt.icon}</span>
              <span>{opt.label}</span>
            </button>
          ))}
        </div>
        {/* Hint for selected trigger */}
        <p className="text-xs" style={{ color: 'var(--accent-500)', marginTop: 5, minHeight: '1.2em' }}>
          {activeTriggerMeta.hint}
        </p>
      </div>

      {/* Zone name */}
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

      {/* Actions */}
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
