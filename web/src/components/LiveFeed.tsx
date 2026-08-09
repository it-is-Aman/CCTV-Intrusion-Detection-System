import { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react'
import { STREAM_URL } from '../api'
import type { Zone } from '../types'

interface LiveFeedProps {
  zones: Zone[]
  onCanvasClick: (x: number, y: number) => void
  onCanvasDblClick: (x: number, y: number) => void
  drawingPoints: [number, number][]
  isDrawing: boolean
}

export interface LiveFeedHandle {
  getCanvasDimensions: () => { width: number; height: number }
}

/**
 * Live webcam feed panel.
 *
 * Renders an MJPEG <img> with a transparent <canvas> overlay stacked on top.
 * The canvas handles all pointer events (zone drawing) and also draws the
 * in-progress polygon/line preview.  Existing zones are drawn server-side
 * on the annotated MJPEG stream — the canvas only shows the drawing-in-progress.
 */
const LiveFeed = forwardRef<LiveFeedHandle, LiveFeedProps>(function LiveFeed(
  { zones: _zones, onCanvasClick, onCanvasDblClick, drawingPoints, isDrawing },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useImperativeHandle(ref, () => ({
    getCanvasDimensions: () => {
      const canvas = canvasRef.current
      return canvas ? { width: canvas.width, height: canvas.height } : { width: 0, height: 0 }
    },
  }))

  // Resize canvas to match the container
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const resize = () => {
      canvas.width = container.clientWidth
      canvas.height = container.clientHeight
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(container)
    return () => ro.disconnect()
  }, [])

  // Draw in-progress preview
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!isDrawing || drawingPoints.length === 0) return

    const { width: w, height: h } = canvas

    ctx.save()
    ctx.strokeStyle = '#00d4b4'
    ctx.lineWidth = 2
    ctx.setLineDash([6, 3])
    ctx.shadowColor = '#00d4b4'
    ctx.shadowBlur = 6

    ctx.beginPath()
    drawingPoints.forEach(([nx, ny], i) => {
      const px = nx * w
      const py = ny * h
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    })
    ctx.stroke()

    // Draw vertex dots
    ctx.setLineDash([])
    drawingPoints.forEach(([nx, ny], i) => {
      const px = nx * w
      const py = ny * h
      ctx.beginPath()
      ctx.arc(px, py, i === 0 ? 5 : 3.5, 0, Math.PI * 2)
      ctx.fillStyle = i === 0 ? '#00d4b4' : 'rgba(0,212,180,0.7)'
      ctx.fill()
    })

    // Label
    if (drawingPoints.length >= 1) {
      const [nx, ny] = drawingPoints[drawingPoints.length - 1]
      ctx.fillStyle = 'rgba(0,0,0,0.6)'
      ctx.fillRect(nx * w + 8, ny * h - 18, 90, 18)
      ctx.fillStyle = '#00d4b4'
      ctx.font = '11px "JetBrains Mono", monospace'
      ctx.fillText(`${drawingPoints.length} pts — dbl-click to close`, nx * w + 12, ny * h - 5)
    }

    ctx.restore()
  }, [drawingPoints, isDrawing])

  const toNorm = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    }
  }, [])

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = toNorm(e)
    if (pos) onCanvasClick(pos.x, pos.y)
  }, [toNorm, onCanvasClick])

  const handleDblClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = toNorm(e)
    if (pos) onCanvasDblClick(pos.x, pos.y)
  }, [toNorm, onCanvasDblClick])

  return (
    <div className="feed-container" ref={containerRef}>
      <img
        id="mjpeg-feed"
        src={STREAM_URL}
        alt="Live webcam feed"
        className="feed-image"
        draggable={false}
      />
      <canvas
        ref={canvasRef}
        className="feed-canvas"
        onClick={handleClick}
        onDoubleClick={handleDblClick}
        style={{ cursor: isDrawing ? 'crosshair' : 'default' }}
        aria-label="Zone drawing canvas"
      />
    </div>
  )
})

export default LiveFeed
