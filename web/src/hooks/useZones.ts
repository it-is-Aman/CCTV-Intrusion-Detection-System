import { useState, useEffect, useCallback } from 'react'
import { getZones, createZone, deleteZone } from '../api'
import type { Zone, ZoneCreate } from '../types'

interface UseZonesReturn {
  zones: Zone[]
  loading: boolean
  error: string | null
  create: (payload: ZoneCreate) => Promise<Zone>
  remove: (id: string) => Promise<void>
  reload: () => Promise<void>
}

/**
 * Zone CRUD hook with optimistic updates.
 *
 * ``create`` and ``remove`` update local state immediately for snappy UX,
 * then sync with the server.  On error, state is rolled back.
 */
export function useZones(): UseZonesReturn {
  const [zones, setZones] = useState<Zone[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setError(null)
      const data = await getZones()
      setZones(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load zones')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const create = useCallback(async (payload: ZoneCreate): Promise<Zone> => {
    const created = await createZone(payload)
    setZones(prev => [...prev, created])
    return created
  }, [])

  const remove = useCallback(async (id: string): Promise<void> => {
    const prev = zones
    setZones(z => z.filter(zone => zone.id !== id))
    try {
      await deleteZone(id)
    } catch (e) {
      setZones(prev)  // rollback
      throw e
    }
  }, [zones])

  return { zones, loading, error, create, remove, reload }
}
