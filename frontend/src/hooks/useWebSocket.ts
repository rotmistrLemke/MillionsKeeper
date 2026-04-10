import { useEffect, useRef, useCallback } from 'react'
import { useTradingStore } from '../store/tradingStore'

const RECONNECT_DELAY_MS = 3_000
const MAX_RECONNECT_DELAY_MS = 30_000

export function useWebSocket(path: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const delayRef = useRef(RECONNECT_DELAY_MS)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const unmounting = useRef(false)

  const setConnected = useTradingStore((s) => s.setWsConnected)
  const dispatch = useTradingStore((s) => s.dispatchWsMessage)

  const connect = useCallback(() => {
    if (unmounting.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${window.location.host}${path}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      delayRef.current = RECONNECT_DELAY_MS
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string)
        dispatch(msg)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onclose = () => {
      setConnected(false)
      if (!unmounting.current) {
        reconnectTimer.current = setTimeout(() => {
          delayRef.current = Math.min(delayRef.current * 1.5, MAX_RECONNECT_DELAY_MS)
          connect()
        }, delayRef.current)
      }
    }
  }, [path, setConnected, dispatch])

  useEffect(() => {
    unmounting.current = false
    connect()
    return () => {
      unmounting.current = true
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])
}
