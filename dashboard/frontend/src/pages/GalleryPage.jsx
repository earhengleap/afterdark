import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '@/api/client'
import Navbar from '@/components/layout/Navbar'
import FilterBar from '@/components/layout/FilterBar'
import StatsGrid from '@/components/gallery/StatsGrid'
import MediaGrid from '@/components/gallery/MediaGrid'
import MediaViewer from '@/components/viewer/MediaViewer'
import ChatWidget from '@/components/chat/ChatWidget'
import useStore from '@/store/useStore'

export default function GalleryPage() {
  const { filter, sort, search, items, openViewer, viewerOpen } = useStore()
  const { id: deepLinkId } = useParams()   // present when route is /view/:id
  const autoOpenedRef = useRef(false)       // only auto-open once per mount

  useEffect(() => {
    document.title = 'AfterDark'
    api.track({
      page: '/',
      referrer: document.referrer,
      device: /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
    })
  }, [])

  /* Deep-link auto-open: when /view/:id is visited directly, wait for the
     items list to populate then open the viewer modal for that item.
     This is instant if the item is already in the loaded page, or happens
     as soon as the first API batch returns — no separate API call needed. */
  useEffect(() => {
    if (!deepLinkId || viewerOpen || autoOpenedRef.current) return
    if (items.length === 0) return  // wait for gallery to load

    const idx = items.findIndex(x => String(x.message_id) === String(deepLinkId))
    if (idx !== -1) {
      autoOpenedRef.current = true
      openViewer(idx)
    }
  }, [deepLinkId, items, viewerOpen, openViewer])

  const sectionLabel = search
    ? `Results for "${search}"`
    : filter === 'video' ? 'Videos'
    : filter === 'image' ? 'Photos'
    : sort === 'newest'  ? 'Latest'
    : sort === 'largest' ? 'Largest Files'
    : sort === 'ai'      ? 'AI Enhanced'
    : 'Library'

  return (
    <div className="min-h-screen bg-[#111]">
      <Navbar />

      <main className="pt-[60px]">
        <div className="px-3 sm:px-4 md:px-6 lg:px-8 max-w-[1920px] mx-auto">

          {/* Stats strip */}
          <StatsGrid />

          {/* Filter / sort bar */}
          <FilterBar />

          {/* Section header */}
          <div className="flex items-center gap-3 mt-3 mb-4">
            <h1 className="text-white font-bold text-base shrink-0">{sectionLabel}</h1>
            <div className="flex-1 h-px bg-[#222]" />
          </div>

          {/* Content grid */}
          <MediaGrid />
        </div>
      </main>

      <MediaViewer />
      <ChatWidget />
    </div>
  )
}
