/**
 * Shared TypeScript interfaces.
 *
 * These mirror the Pydantic response schemas on the server side.
 * Keep in sync with server/app/routes/*.py response models.
 */

export type ZoneType = 'polygon' | 'line'
export type PolygonTrigger = 'entry' | 'exit'
export type LineTrigger = 'both' | 'a_to_b' | 'b_to_a'

export interface Zone {
  id: string
  name: string
  zone_type: ZoneType
  /** Normalised [0,1] coordinate pairs [[x,y], ...] */
  points: [number, number][]
  trigger: string
  created_at: string
}

export interface ZoneCreate {
  name: string
  zone_type: ZoneType
  points: [number, number][]
  trigger: string
}

export interface Event {
  id: string
  zone_id: string
  zone_name: string
  track_id: number
  timestamp: string
  snapshot_path: string | null
  clip_path: string | null
  has_snapshot: boolean
  has_clip: boolean
}

export interface PaginatedEvents {
  items: Event[]
  limit: number
  offset: number
  count: number
}

/** WebSocket message types */
export interface WsCrossingMessage {
  type: 'crossing'
  event: Event
}

export type WsMessage = WsCrossingMessage

/** Canvas drawing state */
export interface DrawingPoint {
  x: number  // normalised 0–1
  y: number  // normalised 0–1
}

export type DrawMode = 'polygon' | 'line' | null
