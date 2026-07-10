import { useEffect, useCallback, useRef } from 'react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'

const PAGE_SIZE = 100

export function useMedia() {
  const {
    items,
    loading,
    hasMore,
    filter,
    sort,
    search,
    totalCount,
    health,
    setItems,
    appendItems,
    setLoading,
    addToast,
  } = useStore()

  const abortRef = useRef(null)
  const autoSyncedRef = useRef(false) // ensure we only auto-sync once per session
  const prevServerTotalRef = useRef(null) // track last known server total for auto-refresh

  const fetchItems = useCallback(
    async (offset = 0, replace = true) => {
      if (abortRef.current) abortRef.current.abort()
      abortRef.current = new AbortController()

      setLoading(true)
      try {
        const data = await api.getMedia({
          limit: PAGE_SIZE,
          offset,
          filter,
          sort,
          search,
          signal: abortRef.current.signal,
        })
        const list = Array.isArray(data) ? data : (data.items || [])
        const total = data.total ?? data.total_count ?? list.length

        if (replace) {
          setItems(list, total) // also sets totalCount + hasMore

          // Auto-sync: if the index came back empty on first load, trigger a sync
          // so the backend fetches from Telegram and the gallery populates itself.
          if (list.length === 0 && !autoSyncedRef.current) {
            autoSyncedRef.current = true
            addToast('Gallery is empty — syncing from Telegram…', 'info')
            api.sync().then((result) => {
              const synced = result.total ?? result.new_items ?? result.count ?? 0
              if (synced > 0) {
                addToast(`Sync complete — ${synced.toLocaleString()} item${synced !== 1 ? 's' : ''} loaded`, 'success')
                fetchItems(0, true) // re-fetch after sync
              } else {
                addToast('Sync finished — no media found in the group', 'warning')
              }
            }).catch((err) => {
              addToast('Auto-sync failed: ' + (err.message || 'Check backend logs'), 'error')
            })
          }
        } else {
          appendItems(list)
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          addToast('Failed to load media. Is the backend running?', 'error')
        }
      } finally {
        setLoading(false)
      }
    },
    [filter, sort, search, setItems, appendItems, setLoading, addToast]
  )

  // Fetch on mount and whenever filters/sort/search change
  useEffect(() => {
    fetchItems(0, true)

    return () => {
      if (abortRef.current) abortRef.current.abort()
    }
  }, [filter, sort, search]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      fetchItems(items.length, false)
    }
  }, [loading, hasMore, items.length, fetchItems])

  const refresh = useCallback(() => {
    fetchItems(0, true)
  }, [fetchItems])

  // Auto-refresh gallery when backend reports more items than we currently show
  useEffect(() => {
    const serverTotal = health?.total_media ?? health?.total_count ?? health?.cached_items ?? health?.stats?.total ?? 0
    if (serverTotal === 0) return

    // On first health response, just record the baseline
    if (prevServerTotalRef.current === null) {
      prevServerTotalRef.current = serverTotal
      return
    }

    // If the server now has more items than before refresh
    if (serverTotal > prevServerTotalRef.current) {
      prevServerTotalRef.current = serverTotal
      fetchItems(0, true)
    } else {
      prevServerTotalRef.current = serverTotal
    }
  }, [health]) // eslint-disable-line react-hooks/exhaustive-deps

  return { items, totalCount, loading, hasMore, loadMore, refresh }
}
