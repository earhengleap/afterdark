"use client"

import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Search, Sparkles, RefreshCw, ArrowUp, Play, X, ChevronLeft, ChevronRight, Copy, Download } from "lucide-react"
import { cn, formatBytes, formatDuration, formatRelative, getAspectRatioClass } from "@/lib/utils"
import type { MediaItem, MediaStats, FilterType, SortType, DensityType } from "@/types"

// Demo data for testing
const demoItems: MediaItem[] = [
  {
    message_id: 1,
    url: "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
    thumb_url: "https://via.placeholder.com/320x180/1a1a1a/666666?text=Video+1",
    media_kind: "video",
    file_name: "demo_video_1.mp4",
    caption: "Demo Video 1",
    ai_title: "Amazing Video Content",
    ai_description: "This is a demo video showing the gallery functionality",
    width: 1920,
    height: 1080,
    size: 50000000,
    duration: 120,
    date: new Date().toISOString(),
    is_cached: true,
  },
  {
    message_id: 2,
    url: "https://sample-videos.com/img/Sample-jpg-image-500kb.jpg",
    media_kind: "image",
    file_name: "demo_image_1.jpg",
    caption: "Demo Image 1",
    ai_title: "Beautiful Image",
    ai_description: "A stunning image showcase",
    width: 1920,
    height: 1080,
    size: 25000000,
    date: new Date(Date.now() - 86400000).toISOString(),
    is_cached: true,
  },
  {
    message_id: 3,
    url: "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_2mb.mp4",
    thumb_url: "https://via.placeholder.com/320x180/1a1a1a/666666?text=Video+2",
    media_kind: "video",
    file_name: "demo_video_2.mp4",
    caption: "Demo Video 2",
    ai_title: "Epic Video Clip",
    ai_description: "Another great video for testing",
    width: 1920,
    height: 1080,
    size: 75000000,
    duration: 180,
    date: new Date(Date.now() - 172800000).toISOString(),
    is_cached: true,
  },
]

export default function GalleryPage() {
  // State
  const [items, setItems] = useState<MediaItem[]>([])
  const [filtered, setFiltered] = useState<MediaItem[]>([])
  const [filter, setFilter] = useState<FilterType>("all")
  const [sort, setSort] = useState<SortType>("newest")
  const [search, setSearch] = useState("")
  const [density, setDensity] = useState<DensityType>("dense")
  const [stats, setStats] = useState<MediaStats>({ total: 0, videos: 0, images: 0, bytes: 0 })
  const [syncing, setSyncing] = useState(false)
  const [retitling, setRetitling] = useState(false)
  const [visibleCount, setVisibleCount] = useState(36)
  const [viewerIndex, setViewerIndex] = useState(-1)
  const [isMobile, setIsMobile] = useState(false)
  const [mounted, setMounted] = useState(false)

  // Check mobile only after mount
  useEffect(() => {
    setMounted(true)
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener("resize", checkMobile)
    return () => window.removeEventListener("resize", checkMobile)
  }, [])

  // Fetch media
  const loadMedia = useCallback(async () => {
    try {
      const res = await fetch("/api/media/page?limit=240")
      if (!res.ok) {
        // Load demo data if API fails
        setItems(demoItems)
        setFiltered(demoItems)
        setStats({ total: 3, videos: 2, images: 1, bytes: 150000000 })
        return
      }
      const data = await res.json()
      
      if (data.items && data.items.length > 0) {
        const normalized = data.items.map((item: MediaItem) => ({
          ...item,
          ai_title: item.ai_title || "",
          ai_description: item.ai_description || "",
          url: item.url || "",
          thumb_url: item.thumb_url || item.url || "",
        }))
        setItems(normalized)
        setFiltered(normalized)
        
        if (data.stats) {
          setStats({
            total: Number(data.stats.total) || 0,
            videos: Number(data.stats.videos) || 0,
            images: Number(data.stats.images) || 0,
            bytes: Number(data.stats.bytes) || 0,
          })
        }
      } else {
        // Load demo data if no items
        setItems(demoItems)
        setFiltered(demoItems)
        setStats({ total: 3, videos: 2, images: 1, bytes: 150000000 })
      }
    } catch (err) {
      console.error("Failed to load media:", err)
      // Load demo data on error
      setItems(demoItems)
      setFiltered(demoItems)
      setStats({ total: 3, videos: 2, images: 1, bytes: 150000000 })
    }
  }, [])

  useEffect(() => {
    loadMedia()
  }, [loadMedia])

  // Filter and sort
  useEffect(() => {
    let result = [...items]

    if (filter !== "all") {
      result = result.filter(item => item.media_kind === filter)
    }

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(item => {
        const fields = [
          item.ai_title,
          item.ai_description,
          item.caption,
          item.file_name,
        ].filter(Boolean).join(" ").toLowerCase()
        return fields.includes(q)
      })
    }

    // Sort
    result.sort((a, b) => {
      const dateA = new Date(a.date).getTime()
      const dateB = new Date(b.date).getTime()
      
      switch (sort) {
        case "oldest":
          return dateA - dateB
        case "largest":
          return (b.size || 0) - (a.size || 0)
        case "ai":
          const aHasAI = a.ai_title || a.ai_description
          const bHasAI = b.ai_title || b.ai_description
          if (aHasAI !== bHasAI) return bHasAI ? 1 : -1
          return dateB - dateA
        default:
          return dateB - dateA
      }
    })

    setFiltered(result)
    setVisibleCount(Math.min(36, result.length))
  }, [items, filter, search, sort])

  // Sync
  const handleSync = async () => {
    setSyncing(true)
    try {
      const res = await fetch("/api/sync?limit=all&wait_seconds=3", { method: "POST" })
      if (res.ok) {
        await loadMedia()
      }
    } catch (err) {
      console.error("Sync failed:", err)
    }
    setSyncing(false)
  }

  // AI Enhance
  const handleAI = async () => {
    setRetitling(true)
    try {
      await fetch("/api/ai-titles?mode=style&batch_size=25", { method: "POST" })
      await loadMedia()
    } catch (err) {
      console.error("AI failed:", err)
    }
    setRetitling(false)
  }

  // Open viewer
  const openViewer = (index: number) => {
    setViewerIndex(index)
    document.body.style.overflow = "hidden"
  }

  const closeViewer = () => {
    setViewerIndex(-1)
    document.body.style.overflow = ""
  }

  // Navigate viewer
  const navigateViewer = (dir: number) => {
    const newIndex = viewerIndex + dir
    if (newIndex >= 0 && newIndex < filtered.length) {
      setViewerIndex(newIndex)
    }
  }

  // Load more
  const loadMore = () => {
    setVisibleCount(prev => Math.min(prev + 36, filtered.length))
  }

  // Get current viewer item
  const viewerItem = viewerIndex >= 0 ? filtered[viewerIndex] : null

  // Get suggested items
  const suggestedItems = viewerItem 
    ? filtered.filter(item => item.media_kind === viewerItem.media_kind && item.message_id !== viewerItem.message_id).slice(0, 6)
    : []

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-white">
      {/* Background Orbs */}
      <div className="orb orb-primary w-[400px] h-[400px] -top-[200px] -left-[200px] animate-pulse" style={{ animationDuration: '8s' }} />
      <div className="orb orb-secondary w-[500px] h-[500px] bottom-0 right-0 animate-pulse" style={{ animationDuration: '12s' }} />
      <div className="orb orb-accent w-[300px] h-[300px] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" style={{ animationDuration: '10s' }} />

      {/* Header */}
      <motion.header 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="sticky top-0 z-50 bg-[#0d0d0d]/80 backdrop-blur-xl border-b border-white/5"
      >
        <div className="max-w-7xl mx-auto px-4 py-4">
          {/* Top Row */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
            {/* Brand */}
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2 py-0.5 bg-[#ff4757] text-white text-[10px] font-bold rounded-full uppercase">18+</span>
                <span className="px-2 py-0.5 border border-white/10 text-[#a0a0a0] text-[10px] font-bold rounded-full uppercase">AI Vault</span>
              </div>
              <h1 className="text-2xl md:text-3xl font-bold">AfterDark Vault</h1>
              <p className="text-[#666] text-xs uppercase tracking-wider mt-1">Intelligent Media Gallery</p>
            </div>

            {/* Search */}
            <div className="flex-1 max-w-md">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#666]" />
                <input
                  type="text"
                  placeholder="Search titles, descriptions..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full bg-[#1a1a1a] border border-white/8 rounded-full py-2.5 pl-11 pr-4 text-sm outline-none focus:border-[#ff4757]/50 transition-colors"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleSync}
                disabled={syncing}
                className="flex items-center gap-2 px-4 py-2 bg-[#ff4757] hover:bg-[#ff6b81] disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors"
              >
                <RefreshCw className={cn("w-4 h-4", syncing && "animate-spin")} />
                <span className="hidden sm:inline">Sync</span>
              </button>
              <button
                onClick={handleAI}
                disabled={retitling}
                className="flex items-center gap-2 px-4 py-2 border border-[#2ed573]/30 text-[#2ed573] hover:bg-[#2ed573]/10 rounded-lg text-sm font-semibold transition-colors"
              >
                <Sparkles className={cn("w-4 h-4", retitling && "animate-pulse")} />
                <span className="hidden sm:inline">AI</span>
              </button>
              <button
                onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
                className="p-2 border border-white/8 hover:bg-white/5 rounded-lg transition-colors"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {/* Tabs */}
              <div className="flex bg-[#1a1a1a] rounded-full p-1">
                {(["all", "video", "image"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={cn(
                      "px-4 py-1.5 rounded-full text-xs font-semibold transition-colors capitalize",
                      filter === f 
                        ? "bg-[#ff4757] text-white" 
                        : "text-[#666] hover:text-white"
                    )}
                  >
                    {f === "all" ? "All" : f === "video" ? "Videos" : "Images"}
                  </button>
                ))}
              </div>

              {/* Sort */}
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortType)}
                className="bg-[#1a1a1a] border border-white/8 rounded-lg px-3 py-1.5 text-xs outline-none focus:border-[#ff4757]/50"
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="largest">Largest</option>
                <option value="ai">AI Enhanced</option>
              </select>
            </div>

            {/* Meta */}
            <div className="flex items-center gap-4 text-xs text-[#666]">
              <span>{filtered.length} items</span>
            </div>
          </div>
        </div>
      </motion.header>

      {/* Stats */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Total", value: stats.total },
            { label: "Videos", value: stats.videos },
            { label: "Images", value: stats.images },
            { label: "Storage", value: formatBytes(stats.bytes) },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="bg-[#141414] border border-white/8 rounded-xl p-4"
            >
              <p className="text-[#666] text-xs uppercase tracking-wider mb-1">{stat.label}</p>
              <p className="text-2xl font-bold">{typeof stat.value === "number" ? stat.value.toLocaleString() : stat.value}</p>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div className="max-w-7xl mx-auto px-4 pb-20">
        {filtered.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-6xl mb-4 opacity-20">🔍</div>
            <p className="text-[#666]">No media found</p>
            <p className="text-[#444] text-sm mt-2">Try adjusting your search or sync new content</p>
          </div>
        ) : (
          <>
            <div className={cn(
              "grid gap-3",
              density === "dense" 
                ? "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6" 
                : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
            )}>
              {filtered.slice(0, visibleCount).map((item, i) => (
                <MediaCard 
                  key={item.message_id} 
                  item={item} 
                  index={i} 
                  onClick={() => {
                    const idx = filtered.findIndex(x => x.message_id === item.message_id)
                    openViewer(idx)
                  }}
                />
              ))}
            </div>

            {visibleCount < filtered.length && (
              <div className="text-center mt-8">
                <button
                  onClick={loadMore}
                  className="px-6 py-3 bg-[#1a1a1a] hover:bg-[#242424] border border-white/8 rounded-full text-sm font-semibold transition-colors"
                >
                  Load More
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Viewer Modal */}
      <AnimatePresence>
        {viewerIndex >= 0 && viewerItem && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/95 backdrop-blur-xl flex items-center justify-center p-4"
            onClick={closeViewer}
          >
            {/* Close */}
            <button
              onClick={closeViewer}
              className="absolute top-4 right-4 z-10 p-2 bg-white/10 hover:bg-white/20 rounded-full transition-colors"
            >
              <X className="w-6 h-6" />
            </button>

            {/* Navigation */}
            {viewerIndex > 0 && (
              <button
                onClick={(e) => { e.stopPropagation(); navigateViewer(-1) }}
                className="absolute left-4 top-1/2 -translate-y-1/2 z-10 p-3 bg-white/10 hover:bg-white/20 rounded-full transition-colors hidden md:block"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>
            )}
            {viewerIndex < filtered.length - 1 && (
              <button
                onClick={(e) => { e.stopPropagation(); navigateViewer(1) }}
                className="absolute right-4 md:right-[380px] top-1/2 -translate-y-1/2 z-10 p-3 bg-white/10 hover:bg-white/20 rounded-full transition-colors hidden md:block"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            )}

            {/* Content */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className={cn(
                "bg-[#141414] rounded-2xl overflow-hidden flex flex-col md:flex-row max-h-[90vh]",
                isMobile ? "w-full" : "w-full max-w-5xl"
              )}
            >
              {/* Media */}
              <div className={cn(
                "flex-1 flex items-center justify-center bg-black",
                isMobile ? "h-[50vh]" : "min-h-[500px]"
              )}>
                {viewerItem.media_kind === "video" ? (
                  <video
                    src={viewerItem.url}
                    controls
                    autoPlay
                    playsInline
                    className="max-w-full max-h-[85vh] object-contain"
                    onClick={(e) => e.stopPropagation()}
                    onError={(e) => console.log("Video load error:", e)}
                  />
                ) : (
                  <img
                    src={viewerItem.url}
                    alt={viewerItem.ai_title || viewerItem.caption || "Media"}
                    className="max-w-full max-h-[85vh] object-contain"
                    onClick={(e) => e.stopPropagation()}
                    onError={(e) => {
                      console.log("Image load error:", e)
                      const target = e.target as HTMLImageElement
                      target.src = "/placeholder.svg"
                    }}
                  />
                )}
              </div>

              {/* Info Panel */}
              <div className={cn(
                "w-full md:w-[340px] flex flex-col p-5 overflow-y-auto",
                isMobile ? "h-[40vh]" : "max-h-[85vh]"
              )}>
                <h2 className="text-lg font-bold mb-4">{viewerItem.ai_title || viewerItem.caption || "Media"}</h2>
                
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-[#666] text-xs uppercase tracking-wider mb-1">AI Description</p>
                    <p className="text-[#a0a0a0]">{viewerItem.ai_description || "No description"}</p>
                  </div>
                  
                  <div>
                    <p className="text-[#666] text-xs uppercase tracking-wider mb-1">Caption</p>
                    <p className="text-[#a0a0a0]">{viewerItem.caption || "No caption"}</p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <span className="px-3 py-1 bg-[#ff4757]/20 text-[#ff4757] rounded-full text-xs font-semibold">
                      {viewerItem.media_kind.toUpperCase()}
                    </span>
                    <span className="px-3 py-1 bg-white/5 rounded-full text-xs">
                      {formatBytes(viewerItem.size || 0)}
                    </span>
                    <span className="px-3 py-1 bg-white/5 rounded-full text-xs">
                      {formatRelative(viewerItem.date)}
                    </span>
                    {viewerItem.duration && (
                      <span className="px-3 py-1 bg-white/5 rounded-full text-xs">
                        {formatDuration(viewerItem.duration)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 mt-4 pt-4 border-t border-white/5">
                  <button 
                    onClick={() => navigator.clipboard.writeText(viewerItem.url)}
                    className="flex-1 flex items-center justify-center gap-2 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors"
                  >
                    <Copy className="w-4 h-4" /> Copy
                  </button>
                  <a
                    href={viewerItem.url}
                    download
                    className="flex-1 flex items-center justify-center gap-2 py-2 bg-[#ff4757] hover:bg-[#ff6b81] rounded-lg text-sm font-semibold transition-colors"
                  >
                    <Download className="w-4 h-4" /> Download
                  </a>
                </div>

                {/* Suggested */}
                {suggestedItems.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-white/5">
                    <p className="text-sm font-semibold mb-3">Up Next</p>
                    <div className="space-y-2 max-h-[200px] overflow-y-auto">
                      {suggestedItems.map((item) => {
                        const idx = filtered.findIndex(x => x.message_id === item.message_id)
                        return (
                          <button
                            key={item.message_id}
                            onClick={() => setViewerIndex(idx)}
                            className="w-full flex gap-3 p-2 hover:bg-white/5 rounded-lg transition-colors text-left"
                          >
                            <div className="w-20 h-12 bg-[#1a1a1a] rounded overflow-hidden flex-shrink-0">
                              <img src={item.thumb_url || item.url} alt="" className="w-full h-full object-cover" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium truncate">{item.ai_title || item.caption || "Media"}</p>
                              <p className="text-[#666] text-xs">{formatRelative(item.date)}</p>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// Media Card Component
function MediaCard({ item, index, onClick }: { item: MediaItem; index: number; onClick: () => void }) {
  const aspectClass = getAspectRatioClass(item.width || 0, item.height || 0, item.media_kind)
  const hasAI = item.ai_title || item.ai_description

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.5) }}
      whileHover={{ y: -4 }}
      className="group relative bg-[#141414] border border-white/5 rounded-xl overflow-hidden cursor-pointer"
      onClick={onClick}
    >
      {/* AI Badge */}
      {hasAI && (
        <div className="absolute top-2 right-2 z-10 w-5 h-5 bg-[#2ed573] rounded-full shadow-lg" />
      )}

      {/* Thumbnail */}
      <div className={cn("relative bg-[#1a1a1a]", aspectClass)}>
        <img
          src={item.media_kind === "video" 
            ? (item.thumb_url || item.url + "/thumb") 
            : item.url}
          alt={item.ai_title || item.caption || "Media"}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onError={(e) => {
            const target = e.target as HTMLImageElement
            target.src = "/placeholder.svg"
          }}
        />
        
        {/* Video Play Icon */}
        {item.media_kind === "video" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-12 h-12 bg-black/60 rounded-full flex items-center justify-center backdrop-blur-sm">
              <Play className="w-5 h-5 fill-white ml-0.5" />
            </div>
          </div>
        )}

        {/* Duration */}
        {item.duration && (
          <span className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/80 rounded text-xs font-semibold">
            {formatDuration(item.duration)}
          </span>
        )}

        {/* Type Badge */}
        <span className={cn(
          "absolute top-2 left-2 px-2 py-0.5 rounded text-[9px] font-bold uppercase",
          item.media_kind === "video" ? "bg-[#ff4757]" : "bg-[#ffa502]"
        )}>
          {item.media_kind}
        </span>
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-sm font-medium truncate">{item.ai_title || item.caption || "Untitled"}</p>
        <p className="text-[#666] text-xs mt-1 truncate">
          {item.ai_description ? item.ai_description.slice(0, 50) : formatBytes(item.size || 0)}
        </p>
      </div>
    </motion.div>
  )
}
