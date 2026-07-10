import { useState, useEffect, useCallback } from 'react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'

// Frequency to check server health/sync status
export const POLL_INTERVAL = 5000; // 5 seconds

export function useHealth() {
  const { health, setHealth } = useStore()
  const [loading, setLoading] = useState(!health)

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.getHealth()
      setHealth(data)
    } catch {
      // Silently fail for health — don't spam toasts
    } finally {
      setLoading(false)
    }
  }, [setHealth])

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchHealth])

  return { health, loading }
}
