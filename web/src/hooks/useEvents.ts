import { useState, useEffect, useCallback, useRef } from 'react'
import { listEvents } from '../api'
import type { Event, WsMessage } from '../types'

interface UseEventsReturn {
  events: Event[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
  /** Call with the latest WS message to prepend new events without a full reload. */
  onWsMessage: (msg: WsMessage) => void
}

/**
 * Events hook — initial load + real-time prepend on WebSocket crossing events.
 *
 * When a WS crossing message arrives, the new event is prepended to the list
 * immediately (the list is kept in newest-first order matching the API).
 * A background reload fires 6s later to pick up evidence paths once files
 * are written to disk.
 */
export function useEvents(): UseEventsReturn {
  const [events, setEvents] = useState<Event[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const reloadTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const reload = useCallback(async () => {
    try {
      setError(null)
      const data = await listEvents({ limit: 100 })
      setEvents(data.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load events')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const onWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type === 'crossing') {
      // Prepend immediately for instant feedback.
      setEvents(prev => [msg.event, ...prev.slice(0, 99)])

      // Reload after a delay to get evidence file paths.
      if (reloadTimer.current) clearTimeout(reloadTimer.current)
      reloadTimer.current = setTimeout(() => { void reload() }, 6000)
    }
  }, [reload])

  useEffect(() => () => {
    if (reloadTimer.current) clearTimeout(reloadTimer.current)
  }, [])

  return { events, loading, error, reload, onWsMessage }
}
