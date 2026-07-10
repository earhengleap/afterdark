import { useEffect, useRef, useCallback, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import {
  X, ChevronLeft, ChevronRight,
  Download, Copy, ExternalLink,
  Film, ImageIcon, Monitor, HardDrive, Clock, Calendar,
  CheckCircle2, ZoomIn, ZoomOut, Play
} from 'lucide-react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'
import { formatBytes, formatDuration, formatDate } from '@/utils/format'

/* ─────────────────────── helpers ─────────────────────── */

function MetaRow({ icon: Icon, label, value, accent }) {
  if (!value) return null
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
      <div className="flex items-center gap-2.5">
        <div className={`w-6 h-6 rounded-md flex items-center justify-center ${accent}`}>
          <Icon size={11} />
        </div>
        <span className="text-[#666] text-xs tracking-wide">{label}</span>
      </div>
      <span className="text-[#c8c8c8] text-xs font-medium tabular-nums">{value}</span>
    </div>
  )
}

function TypeBadge({ isVideo }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[9px] font-black uppercase tracking-[0.12em]
                      px-2 py-1 rounded-full ${
      isVideo
        ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
        : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
    }`}>
      {isVideo ? <Film size={8} /> : <ImageIcon size={8} />}
      {isVideo ? 'Video' : 'Photo'}
    </span>
  )
}

function SuggestedCard({ item, onClick }) {
  const isVid = item.file_type === 'video' || item.media_kind === 'video'
  const [imgErr, setImgErr] = useState(false)
  return (
    <button
      className="text-left group focus:outline-none focus-visible:ring-1 focus-visible:ring-white/30 rounded-xl"
      onClick={onClick}
    >
      <div className="relative aspect-video rounded-xl overflow-hidden bg-[#1c1c1c]
                      ring-1 ring-white/5 group-hover:ring-white/20 transition-all duration-200">
        {!imgErr ? (
          <img
            src={api.thumbUrl(item.message_id)}
            alt={item.ai_title || item.file_name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={() => setImgErr(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-[#1c1c1c]">
            {isVid ? <Film size={16} className="text-[#333]" /> : <ImageIcon size={16} className="text-[#333]" />}
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
        {isVid && (
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <div className="w-8 h-8 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
              <Play size={11} className="text-black ml-0.5" fill="black" />
            </div>
          </div>
        )}
      </div>
      <p className="mt-1.5 text-[10px] text-[#666] line-clamp-2 group-hover:text-[#999] transition-colors duration-150 leading-snug px-0.5">
        {item.ai_title || item.file_name || 'Untitled'}
      </p>
    </button>
  )
}

/* ─────────────────────── main component ─────────────────────── */

export default function MediaViewer() {
  const {
    viewerOpen, viewerIndex, items,
    openViewer, closeViewer, nextItem, prevItem,
    addToast,
  } = useStore()

  const navigate = useNavigate()
  const skipNavRef = useRef(false) // prevents double-navigate on browser Back

  const videoRef    = useRef(null)
  const touchStartX = useRef(null)

  const [copied,     setCopied]     = useState(false)
  const [imgZoomed,  setImgZoomed]  = useState(false)
  const [mediaError, setMediaError] = useState(false)
  const [retryKey,   setRetryKey]   = useState(0)
  const [muted,      setMuted]      = useState(false)

  const item    = viewerOpen && viewerIndex >= 0 ? items[viewerIndex] : null
  const hasPrev = viewerIndex > 0
  const hasNext = viewerIndex < items.length - 1

  const suggested = viewerOpen
    ? items.filter((_, i) => i !== viewerIndex).slice(0, 8)
    : []

  /* reset on item change */
  useEffect(() => {
    setImgZoomed(false)
    setCopied(false)
    setMediaError(false)
    setRetryKey(0)

    // preload adjacent thumbnails
    ;[viewerIndex - 1, viewerIndex + 1].forEach((i) => {
      if (i >= 0 && i < items.length) {
        const img = new window.Image()
        img.src = api.thumbUrl(items[i].message_id)
      }
    })
  }, [viewerIndex, items])

  /* — URL sync: push /view/:id when a video is open —
     This is free — no API call, no page reload.
     The URL becomes shareable/bookmarkable instantly. */
  useEffect(() => {
    if (!viewerOpen || !item) return
    const targetPath = `/view/${item.message_id}`
    if (window.location.pathname !== targetPath) {
      skipNavRef.current = true
      navigate(targetPath, { replace: false })
      skipNavRef.current = false
    }
    // Update page title to match the media
    const t = item.ai_title || item.file_name || 'AfterDark'
    document.title = `${t} — AfterDark`
  }, [viewerOpen, item?.message_id]) // eslint-disable-line react-hooks/exhaustive-deps

  /* — URL sync: go back to / when viewer closes — */
  useEffect(() => {
    if (!viewerOpen && window.location.pathname.startsWith('/view/')) {
      navigate('/', { replace: true })
      document.title = 'AfterDark'
    }
  }, [viewerOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  /* — Browser Back button: close the modal instead of leaving — */
  useEffect(() => {
    if (!viewerOpen) return
    const onPop = () => { closeViewer() }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [viewerOpen, closeViewer])

  /* keyboard nav */
  useEffect(() => {
    if (!viewerOpen) return
    const onKey = (e) => {
      if (e.key === 'Escape')     closeViewer()
      if (e.key === 'ArrowRight') nextItem()
      if (e.key === 'ArrowLeft')  prevItem()
      if (e.key === ' ')          { e.preventDefault(); togglePlay() }
      if (e.key === 'm')          toggleMute()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [viewerOpen, closeViewer, nextItem, prevItem])

  /* body scroll lock */
  useEffect(() => {
    document.body.style.overflow = viewerOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [viewerOpen])

  const handleVideoError = useCallback((e) => {
    const code = e.target?.error?.code
    if (code === 1 || retryKey < 1) {
      setRetryKey(k => k + 1)
      return
    }
    setMediaError(true)
    addToast('Video failed to load', 'error')
  }, [retryKey, addToast])

  const handlePrev = useCallback(() => { videoRef.current?.pause(); prevItem() }, [prevItem])
  const handleNext = useCallback(() => { videoRef.current?.pause(); nextItem() }, [nextItem])

  const togglePlay = useCallback(() => {
    const v = videoRef.current
    if (!v) return
    v.paused ? v.play() : v.pause()
  }, [])

  const toggleMute = useCallback(() => {
    const v = videoRef.current
    if (v) v.muted = !v.muted
    setMuted(m => !m)
  }, [])

  const handleCopy = () => {
    if (!item) return
    // URL is already /view/:id thanks to the sync effect above
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2200)
      addToast('Link copied to clipboard', 'success')
    })
  }

  const handleTouchStart = (e) => { touchStartX.current = e.touches[0].clientX }
  const handleTouchEnd   = (e) => {
    if (touchStartX.current === null) return
    const dx = e.changedTouches[0].clientX - touchStartX.current
    if (dx > 60)       handlePrev()
    else if (dx < -60) handleNext()
    touchStartX.current = null
  }

  // NOTE: Do NOT early-return here — AnimatePresence must see the conditional
  // to play exit animations correctly.

  const isVideo = item ? (item.file_type === 'video' || item.media_kind === 'video') : false
  const title   = item ? (item.ai_title || item.caption || item.file_name || 'Untitled') : ''

  return (
    <AnimatePresence mode="wait">
      {viewerOpen && item && (
        <div key={`viewer-${item.message_id}`} className="fixed inset-0 z-[200] flex items-center justify-center pointer-events-none">

          {/* ── Backdrop ── */}
          <motion.div
            key="vbdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-black/95 backdrop-blur-md pointer-events-auto"
            onClick={closeViewer}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          />

          {/* ── Modal shell ── */}
          <motion.div
            key="vpanel"
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-[1300px] max-h-[92vh]
                       flex flex-col lg:flex-row pointer-events-auto
                       rounded-2xl overflow-hidden
                       bg-[#0f0f0f]
                       ring-1 ring-white/[0.07]
                       shadow-[0_40px_100px_rgba(0,0,0,0.8)]"
            onClick={(e) => e.stopPropagation()}
          >

            {/* ╔══════════════════════════════════╗
                ║        LEFT — MEDIA STAGE        ║
                ╚══════════════════════════════════╝ */}
            <div
              className="relative flex-1 min-h-0 bg-black flex items-center justify-center overflow-hidden"
              style={{ minHeight: '60vh' }}
            >
              {/* Ambient glow behind media */}
              <div className="absolute inset-0 pointer-events-none">
                <div className={`absolute inset-0 opacity-20 blur-3xl scale-110
                                 ${isVideo ? 'bg-blue-900' : 'bg-rose-900'}`} />
              </div>

              {/* ── Error state ── */}
              {mediaError ? (
                <div className="flex flex-col items-center justify-center gap-4 text-center p-10 z-10">
                  <div className="w-16 h-16 rounded-2xl bg-[#1a1a1a] border border-[#2a2a2a] flex items-center justify-center">
                    {isVideo ? <Film size={28} className="text-[#444]" /> : <ImageIcon size={28} className="text-[#444]" />}
                  </div>
                  <div>
                    <p className="text-[#555] text-sm font-medium mb-1">Failed to load media</p>
                    <p className="text-[#3a3a3a] text-xs">The file may be unavailable</p>
                  </div>
                  <a
                    href={api.fileUrl(item.message_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 h-9 px-4 rounded-lg bg-white text-black text-xs font-bold
                               hover:bg-white/90 transition-colors"
                  >
                    <ExternalLink size={12} />
                    Open Directly
                  </a>
                </div>

              /* ── Video ── */
              ) : isVideo ? (
                <div className="relative w-full h-full flex items-center justify-center">
                  <video
                    key={`${item.message_id}-${retryKey}`}
                    ref={videoRef}
                    src={api.fileUrl(item.message_id)}
                    poster={api.thumbUrl(item.message_id)}
                    controls
                    playsInline
                    preload="metadata"
                    muted={muted}
                    className="w-full h-full object-contain"
                    style={{ maxHeight: '80vh' }}
                    onError={handleVideoError}
                  />
                </div>

              /* ── Image ── */
              ) : (
                <div
                  className={`relative w-full h-full flex items-center justify-center overflow-hidden
                              ${imgZoomed ? 'cursor-zoom-out' : 'cursor-zoom-in'}`}
                  onClick={() => setImgZoomed(z => !z)}
                >
                  <img
                    key={item.message_id}
                    src={api.fileUrl(item.message_id)}
                    alt={title}
                    className={`max-w-full object-contain transition-transform duration-400 ease-out
                                ${imgZoomed ? 'scale-150 cursor-zoom-out' : 'scale-100'}`}
                    style={{ maxHeight: '80vh' }}
                    onError={(e) => {
                      if (e.target.src !== api.thumbUrl(item.message_id)) {
                        e.target.src = api.thumbUrl(item.message_id)
                      } else {
                        setMediaError(true)
                        addToast('Image failed to load', 'error')
                      }
                    }}
                  />
                  {/* Zoom hint */}
                  <AnimatePresence>
                    {!imgZoomed && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="absolute bottom-4 right-4 flex items-center gap-1.5 bg-black/60
                                   backdrop-blur-sm rounded-lg px-2.5 py-1.5 pointer-events-none
                                   border border-white/10"
                      >
                        <ZoomIn size={11} className="text-white/50" />
                        <span className="text-[10px] text-white/40">Click to zoom</span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  {imgZoomed && (
                    <div className="absolute bottom-4 right-4 flex items-center gap-1.5 bg-black/60
                                    backdrop-blur-sm rounded-lg px-2.5 py-1.5 pointer-events-none
                                    border border-white/10">
                      <ZoomOut size={11} className="text-white/50" />
                      <span className="text-[10px] text-white/40">Click to zoom out</span>
                    </div>
                  )}
                </div>
              )}

              {/* ── Nav: Prev ── */}
              {hasPrev && (
                <button
                  onClick={handlePrev}
                  className="absolute left-3 top-1/2 -translate-y-1/2 z-20
                             w-10 h-10 rounded-full flex items-center justify-center
                             bg-black/60 backdrop-blur-sm border border-white/10
                             hover:bg-white/10 hover:border-white/20 hover:scale-105
                             transition-all duration-150 active:scale-95"
                  aria-label="Previous"
                >
                  <ChevronLeft size={20} className="text-white" />
                </button>
              )}

              {/* ── Nav: Next ── */}
              {hasNext && (
                <button
                  onClick={handleNext}
                  className="absolute right-3 top-1/2 -translate-y-1/2 z-20
                             w-10 h-10 rounded-full flex items-center justify-center
                             bg-black/60 backdrop-blur-sm border border-white/10
                             hover:bg-white/10 hover:border-white/20 hover:scale-105
                             transition-all duration-150 active:scale-95"
                  aria-label="Next"
                >
                  <ChevronRight size={20} className="text-white" />
                </button>
              )}

              {/* ── Position counter ── */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 pointer-events-none
                              flex items-center gap-1.5 bg-black/60 backdrop-blur-sm
                              border border-white/10 rounded-full px-3 py-1">
                {items.slice(Math.max(0, viewerIndex - 2), viewerIndex + 3).map((_, relI) => {
                  const absI = Math.max(0, viewerIndex - 2) + relI
                  return (
                    <div
                      key={absI}
                      className={`rounded-full transition-all duration-200 ${
                        absI === viewerIndex
                          ? 'w-4 h-1.5 bg-white'
                          : 'w-1.5 h-1.5 bg-white/30'
                      }`}
                    />
                  )
                })}
                <span className="text-[10px] text-white/40 ml-1 tabular-nums">
                  {viewerIndex + 1}/{items.length}
                </span>
              </div>
            </div>

            {/* ╔═══════════════════════════════╗
                ║        RIGHT — SIDEBAR        ║
                ╚═══════════════════════════════╝ */}
            <div className="w-full lg:w-[300px] xl:w-[320px] flex flex-col
                            border-t lg:border-t-0 lg:border-l border-white/[0.05]
                            bg-[#0f0f0f] overflow-y-auto">

              {/* ── Header bar (title + close) ── */}
              <div className="flex items-start justify-between gap-3 p-5 border-b border-white/[0.05]">
                <div className="flex-1 min-w-0">
                  <TypeBadge isVideo={isVideo} />
                  <h2 className="text-white font-semibold text-[13px] leading-snug line-clamp-3 mt-2">
                    {title}
                  </h2>
                  {item.caption && item.caption !== title && (
                    <p className="text-[#555] text-[11px] mt-1.5 line-clamp-2 leading-relaxed">
                      {item.caption}
                    </p>
                  )}
                  {item.ai_description && (
                    <p className="text-[#444] text-[11px] mt-2 italic leading-relaxed line-clamp-3">
                      {item.ai_description}
                    </p>
                  )}
                </div>

                <button
                  onClick={closeViewer}
                  className="shrink-0 w-8 h-8 rounded-xl flex items-center justify-center
                             bg-white/5 border border-white/[0.07]
                             hover:bg-white/10 hover:border-white/15
                             text-[#666] hover:text-white
                             transition-all duration-150"
                  aria-label="Close viewer"
                >
                  <X size={14} />
                </button>
              </div>

              {/* ── File details ── */}
              <div className="px-5 py-4 border-b border-white/[0.05]">
                <p className="text-[#3a3a3a] text-[9px] font-black uppercase tracking-[0.15em] mb-3">
                  File Details
                </p>
                <MetaRow
                  icon={Monitor}
                  label="Resolution"
                  value={item.width && item.height ? `${item.width}×${item.height}` : null}
                  accent="bg-cyan-500/15 text-cyan-400"
                />
                <MetaRow
                  icon={HardDrive}
                  label="File Size"
                  value={formatBytes(item.file_size)}
                  accent="bg-emerald-500/15 text-emerald-400"
                />
                {isVideo && (
                  <MetaRow
                    icon={Clock}
                    label="Duration"
                    value={formatDuration(item.duration)}
                    accent="bg-violet-500/15 text-violet-400"
                  />
                )}
                <MetaRow
                  icon={Calendar}
                  label="Added"
                  value={formatDate(item.timestamp)}
                  accent="bg-rose-500/15 text-rose-400"
                />
              </div>

              {/* ── Actions ── */}
              <div className="px-5 py-4 border-b border-white/[0.05] flex flex-col gap-2">
                {/* Primary: Download */}
                <a
                  href={api.fileUrl(item.message_id)}
                  download
                  className="group flex items-center justify-center gap-2 h-10 rounded-xl
                             bg-white text-black text-[12px] font-bold
                             hover:bg-white/90 active:scale-[0.98]
                             transition-all duration-150"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Download size={14} className="group-hover:-translate-y-0.5 transition-transform duration-150" />
                  Download File
                </a>

                {/* Secondary row */}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={handleCopy}
                    className="flex items-center justify-center gap-1.5 h-9 rounded-xl
                               bg-white/5 border border-white/[0.07]
                               hover:bg-white/8 hover:border-white/12
                               text-[#888] hover:text-white
                               text-[11px] transition-all duration-150"
                  >
                    <AnimatePresence mode="wait">
                      {copied ? (
                        <motion.span
                          key="c"
                          initial={{ scale: 0.6, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          exit={{ scale: 0.6, opacity: 0 }}
                          className="flex items-center gap-1 text-emerald-400"
                        >
                          <CheckCircle2 size={13} />
                          Copied!
                        </motion.span>
                      ) : (
                        <motion.span
                          key="u"
                          initial={{ scale: 0.6, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          exit={{ scale: 0.6, opacity: 0 }}
                          className="flex items-center gap-1"
                        >
                          <Copy size={13} />
                          Copy Link
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </button>

                  <a
                    href={api.fileUrl(item.message_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-1.5 h-9 rounded-xl
                               bg-white/5 border border-white/[0.07]
                               hover:bg-white/8 hover:border-white/12
                               text-[#888] hover:text-white
                               text-[11px] transition-all duration-150"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink size={13} />
                    Open Tab
                  </a>
                </div>
              </div>

              {/* ── "Up Next" / Suggested ── */}
              {suggested.length > 0 && (
                <div className="px-5 py-4 flex-1">
                  <p className="text-[#3a3a3a] text-[9px] font-black uppercase tracking-[0.15em] mb-3">
                    More Like This
                  </p>
                  <div className="grid grid-cols-2 gap-2.5">
                    {suggested.map((s) => (
                      <SuggestedCard
                        key={s.message_id}
                        item={s}
                        onClick={() => openViewer(items.findIndex(x => x.message_id === s.message_id))}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* ── Bottom padding spacer ── */}
              <div className="h-4 shrink-0" />
            </div>

          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
