import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsMessage } from '../types'

export type ReadyState = 'connecting' | 'open' | 'closed'

interface UseWebSocketReturn {
  lastMessage: WsMessage | null
  readyState: ReadyState
}

/**
 * WebSocket hook with automatic reconnection.
 *
 * On component unmount or URL change, the socket is cleanly closed.
 * Reconnects on close after a short delay (exponential back-off capped at 8s).
 */
export function useWebSocket(url: string): UseWebSocketReturn {
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null)
  const [readyState, setReadyState] = useState<ReadyState>('connecting')
  const socketRef = useRef<WebSocket | null>(null)
  const retryDelay = useRef(1000)
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)

  const connect = useCallback(() => {
    if (unmounted.current) return

    setReadyState('connecting')
    const ws = new WebSocket(url)
    socketRef.current = ws

    ws.onopen = () => {
      if (unmounted.current) { ws.close(); return }
      setReadyState('open')
      retryDelay.current = 1000  // reset back-off on successful connect
    }

    ws.onmessage = (e: MessageEvent) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage
        setLastMessage(msg)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      if (unmounted.current) return
      setReadyState('closed')
      // Reconnect with exponential back-off (max 8s)
      retryTimer.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * 1.5, 8000)
        connect()
      }, retryDelay.current)
    }

    ws.onerror = () => {
      ws.close()  // triggers onclose → reconnect
    }
  }, [url])

  useEffect(() => {
    unmounted.current = false
    connect()

    return () => {
      unmounted.current = true
      if (retryTimer.current) clearTimeout(retryTimer.current)
      socketRef.current?.close()
    }
  }, [connect])

  return { lastMessage, readyState }
}
