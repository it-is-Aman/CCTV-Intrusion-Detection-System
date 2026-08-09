/**
 * Typed API client.
 *
 * All fetch calls go through these helpers so we have:
 * - A single place to change base URLs / auth headers later.
 * - Typed request and response bodies.
 * - Consistent error handling.
 */

import type { Zone, ZoneCreate, Event, PaginatedEvents } from './types'

const BASE = ''  // Vite proxies /zones, /events, /stream, /ws → :8000

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  // 204 No Content
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Zones ────────────────────────────────────────────────────────────────────

export async function getZones(): Promise<Zone[]> {
  return _fetch<Zone[]>('/zones/')
}

export async function createZone(payload: ZoneCreate): Promise<Zone> {
  return _fetch<Zone>('/zones/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteZone(id: string): Promise<void> {
  return _fetch<void>(`/zones/${id}`, { method: 'DELETE' })
}

// ── Events ───────────────────────────────────────────────────────────────────

export interface ListEventsParams {
  zone_id?: string
  limit?: number
  offset?: number
}

export async function listEvents(params: ListEventsParams = {}): Promise<PaginatedEvents> {
  const qs = new URLSearchParams()
  if (params.zone_id) qs.set('zone_id', params.zone_id)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString() ? `?${qs}` : ''
  return _fetch<PaginatedEvents>(`/events/${query}`)
}

export async function getEvent(id: string): Promise<Event> {
  return _fetch<Event>(`/events/${id}`)
}

// ── Media URLs (served directly) ─────────────────────────────────────────────

export const STREAM_URL = '/stream'
export const WS_URL = `ws://${window.location.host}/ws`

export function snapshotUrl(eventId: string): string {
  return `/events/${eventId}/snapshot`
}

export function clipUrl(eventId: string): string {
  return `/events/${eventId}/clip`
}
