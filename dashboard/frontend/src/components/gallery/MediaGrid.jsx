import { useEffect, useRef } from 'react'
import { Film, SearchX } from 'lucide-react'
import { useMedia } from '@/hooks/useMedia'
import MediaCard from './MediaCard'
import SkeletonCard from './SkeletonCard'
import useStore from '@/store/useStore'

const SKELETON_COUNT = 20

export default function MediaGrid() {
  const { items, loading, hasMore, loadMore } = useMedia()
  const { layout, openViewer, search, filter } = useStore()
  const sentinelRef = useRef(null)
  const observerRef = useRef(null)

  const isCompact = layout === 'compact'

  // Explicit responsive column counts — mimics PH layout
  const gridClass = isCompact
    ? 'grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-2 sm:gap-3'
    : 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 sm:gap-4'

  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect()

    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !loading && hasMore) loadMore()
      },
      { rootMargin: '900px' }
    )

    if (sentinelRef.current) observerRef.current.observe(sentinelRef.current)
    return () => observerRef.current?.disconnect()
  }, [loading, hasMore, loadMore])

  /* ── Initial skeleton ── */
  if (loading && items.length === 0) {
    return (
      <div className={gridClass}>
        {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
          <SkeletonCard key={i} index={i} />
        ))}
      </div>
    )
  }

  /* ── Empty state ── */
  if (!loading && items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <div className="w-20 h-20 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] flex items-center justify-center">
          {search
            ? <SearchX size={32} className="text-[#444]" />
            : <Film size={32} className="text-[#444]" />
          }
        </div>
        <div className="text-center">
          <p className="text-white/70 font-semibold text-base">
            {search ? `No results for "${search}"` : 'No media found'}
          </p>
          <p className="text-[#555] text-sm mt-1">
            {filter !== 'all'
              ? `No ${filter}s in your library yet`
              : search
                ? 'Try a different search term'
                : 'Sync from Telegram to get started'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className={gridClass}>
        {items.map((item, index) => (
          <MediaCard
            key={item.message_id}
            item={item}
            index={index}
            onClick={() => openViewer(index)}
          />
        ))}

        {/* Loading more */}
        {loading && items.length > 0 &&
          Array.from({ length: 8 }).map((_, i) => (
            <SkeletonCard key={`sk-${i}`} index={i} />
          ))
        }
      </div>

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} className="h-4 mt-4" />

      {/* End of list */}
      {!hasMore && items.length > 0 && (
        <div className="flex items-center gap-4 justify-center py-10">
          <div className="h-px flex-1 max-w-32 bg-[#2a2a2a]" />
          <span className="text-[#444] text-xs font-medium">All caught up</span>
          <div className="h-px flex-1 max-w-32 bg-[#2a2a2a]" />
        </div>
      )}
    </>
  )
}
