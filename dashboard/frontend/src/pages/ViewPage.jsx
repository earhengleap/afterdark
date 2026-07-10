import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Download, Copy, ExternalLink,
  Film, Image, HardDrive, Clock, Calendar,
  Monitor, CheckCircle2
} from 'lucide-react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'
import { formatBytes, formatDuration, formatDate } from '@/utils/format'

function RelatedCard({ item }) {
  const isVid = item.file_type === 'video' || item.media_kind === 'video'
  return (
    <Link to={`/view/${item.message_id}`} className="group block">
      <div className="relative aspect-video rounded-lg overflow-hidden bg-[#1c1c1c]
                      outline outline-2 outline-transparent group-hover:outline-accent/60
                      transition-[outline-color] duration-150">
        <img
          src={api.thumbUrl(item.message_id)}
          alt={item.ai_title || item.file_name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 will-change-transform"
          loading="lazy"
          onError={(e) => { e.target.style.display = 'none' }}
        />
        {isVid && (
          <div className="absolute inset-0 flex items-center justify-center
                          opacity-0 group-hover:opacity-100 transition-opacity duration-150">
            <div className="w-7 h-7 rounded-full bg-accent/90 flex items-center justify-center">
              <Film size={11} className="text-black ml-px" />
            </div>
          </div>
        )}
      </div>
      <p className="mt-1.5 text-[12px] text-[#aaa] line-clamp-2
                    group-hover:text-accent transition-colors duration-150 leading-snug">
        {item.ai_title || item.file_name || 'Untitled'}
      </p>
    </Link>
  )
}

export default function ViewPage() {
  const { id } = useParams()
  const { addToast } = useStore()
  const [media, setMedia]   = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)
  const [copied, setCopied]   = useState(false)
  const [imgZoomed, setImgZoomed] = useState(false)
  const [videoBuffering, setVideoBuffering] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setMedia(null)
    setVideoBuffering(true)

    api.getMediaById(id)
      .then((data) => {
        setMedia(data)
        document.title = `${data.ai_title || data.file_name || 'AfterDark Media'} — AfterDark`
        api.track({ page: `/view/${id}`, referrer: document.referrer })
      })
      .catch(() => addToast('Failed to load media item', 'error'))
      .finally(() => setLoading(false))

    api.getMedia({ limit: 20, offset: 0, sort: 'newest' })
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.items || [])
        setRelated(list.filter((x) => String(x.message_id) !== String(id)))
      })
      .catch(() => {})
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleCopy = () => {
    const url = `${window.location.origin}/view/${id}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      addToast('URL copied to clipboard', 'success')
    })
  }

  const isVideo = media?.file_type === 'video' || media?.media_kind === 'video'
  const title   = media?.ai_title || media?.file_name || 'Untitled'

  return (
    <div className="min-h-screen bg-[#111]">

      {/* ── Top bar ── */}
      <div className="sticky top-0 z-40 bg-[#1b1b1b] border-b border-[#2a2a2a]">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 h-[54px] flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-1.5 text-[#888] hover:text-accent transition-colors group shrink-0"
          >
            <ArrowLeft size={16} className="group-hover:-translate-x-0.5 transition-transform" />
            <span className="text-sm font-medium hidden sm:inline">Back</span>
          </Link>

          <Link to="/" className="flex items-center no-tap-highlight select-none shrink-0">
            <span className="font-black text-[18px] text-white leading-none tracking-tight">After</span>
            <span className="ml-1 font-black text-[16px] px-[6px] py-[1px] bg-accent text-black rounded leading-snug tracking-tight">Dark</span>
          </Link>

          <div className="flex-1 min-w-0">
            {media && <p className="text-[#bbb] text-sm font-medium truncate">{title}</p>}
          </div>

          {media && (
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={handleCopy} className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-[#222] hover:bg-[#2a2a2a] text-[#aaa] text-[12px] border border-[#333] transition-colors">
                {copied ? <CheckCircle2 size={13} className="text-green-400" /> : <Copy size={13} />}
                <span className="hidden sm:inline">{copied ? 'Copied!' : 'Copy'}</span>
              </button>
              <a
                href={api.fileUrl(media.message_id)}
                download
                className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-accent hover:bg-accent-hover text-black text-[12px] font-bold transition-colors"
              >
                <Download size={13} />
                <span className="hidden sm:inline">Download</span>
              </a>
            </div>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      {loading ? (
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-5">
            <div className="aspect-video shimmer-bg rounded-xl" />
            <div className="space-y-3">
              <div className="h-28 shimmer-bg rounded-xl" />
              <div className="h-44 shimmer-bg rounded-xl" />
            </div>
          </div>
        </div>
      ) : !media ? (
        <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
          <Film size={48} className="text-[#333]" />
          <p className="text-[#666] text-lg">Media not found</p>
          <Link to="/" className="flex items-center gap-2 h-9 px-4 rounded-lg bg-accent text-black text-sm font-bold">
            <ArrowLeft size={15} /> Back to Gallery
          </Link>
        </div>
      ) : (
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-5">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] xl:grid-cols-[1fr_320px] gap-5">

            {/* ── Player column ── */}
            <div className="card-appear">

              {/* Player box */}
              <div className="relative bg-black rounded-xl overflow-hidden aspect-video">
                {isVideo ? (
                  <>
                    {videoBuffering && (
                      <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
                        <div className="w-12 h-12 rounded-full bg-black/60 flex items-center justify-center border border-white/10">
                          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                        </div>
                      </div>
                    )}
                    <video
                      key={media.message_id}
                      src={api.fileUrl(media.message_id)}
                      poster={api.thumbUrl(media.message_id)}
                      controls
                      playsInline
                      preload="metadata"
                      className="w-full h-full object-contain"
                      onCanPlay={() => setVideoBuffering(false)}
                      onPlaying={() => setVideoBuffering(false)}
                      onWaiting={() => setVideoBuffering(true)}
                      onError={(e) => {
                        if (e.target?.error?.code !== 1) {
                          setVideoBuffering(false)
                          addToast('Video failed to load — try downloading', 'error')
                        }
                      }}
                    />
                  </>
                ) : (
                  <img
                    src={api.fileUrl(media.message_id)}
                    alt={title}
                    className={`w-full h-full object-contain transition-transform duration-300
                                ${imgZoomed ? 'scale-150 cursor-zoom-out' : 'cursor-zoom-in'}`}
                    onClick={() => setImgZoomed((z) => !z)}
                    onError={(e) => { e.target.src = api.thumbUrl(media.message_id) }}
                  />
                )}
              </div>

              {/* Title */}
              <div className="mt-4">
                <div className="flex items-start gap-2 mb-1">
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 mt-0.5
                                   ${isVideo ? 'bg-blue-500/15 text-blue-400' : 'bg-pink-500/15 text-pink-400'}`}>
                    {isVideo ? 'VIDEO' : 'PHOTO'}
                  </span>
                  <h1 className="text-white font-semibold text-[15px] leading-snug">{title}</h1>
                </div>
                {media.caption && media.caption !== title && (
                  <p className="text-[#666] text-sm mt-1 ml-[42px]">{media.caption}</p>
                )}
                {media.ai_description && (
                  <p className="text-[#555] text-sm italic mt-2 leading-relaxed ml-[42px]">{media.ai_description}</p>
                )}
              </div>

              {/* Action row */}
              <div className="flex items-center gap-2 mt-4 pb-5 border-b border-[#222]">
                <a
                  href={api.fileUrl(media.message_id)}
                  download
                  className="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-accent hover:bg-accent-hover text-black text-[13px] font-bold transition-colors"
                >
                  <Download size={14} />
                  Download
                </a>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-[#1e1e1e] hover:bg-[#252525] text-[#aaa] text-[13px] border border-[#333] transition-colors"
                >
                  {copied ? <CheckCircle2 size={14} className="text-green-400" /> : <Copy size={14} />}
                  {copied ? 'Copied!' : 'Copy URL'}
                </button>
                <a
                  href={api.fileUrl(media.message_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 h-9 px-3 rounded-lg bg-[#1e1e1e] hover:bg-[#252525] text-[#aaa] text-[13px] border border-[#333] transition-colors"
                  title="Open in new tab"
                >
                  <ExternalLink size={14} />
                </a>
              </div>

              {/* Related grid */}
              {related.length > 0 && (
                <div className="mt-5">
                  <div className="flex items-center gap-3 mb-3">
                    <h2 className="text-white font-bold text-sm shrink-0">More</h2>
                    <div className="flex-1 h-px bg-[#222]" />
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                    {related.slice(0, 12).map((r) => (
                      <RelatedCard key={r.message_id} item={r} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ── Sidebar ── */}
            <div className="flex flex-col gap-3 card-appear" style={{ animationDelay: '60ms' }}>

              {/* Details */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
                <p className="text-[#444] text-[10px] font-bold uppercase tracking-wider mb-3">Details</p>
                <div className="space-y-2.5">
                  {media.width && media.height && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Monitor size={12} className="text-accent" />
                        <span className="text-[#666] text-xs">Resolution</span>
                      </div>
                      <span className="text-[#ccc] text-xs font-medium">{media.width}×{media.height}</span>
                    </div>
                  )}
                  {media.file_size > 0 && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <HardDrive size={12} className="text-green-400" />
                        <span className="text-[#666] text-xs">Size</span>
                      </div>
                      <span className="text-[#ccc] text-xs font-medium">{formatBytes(media.file_size)}</span>
                    </div>
                  )}
                  {isVideo && media.duration > 0 && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Clock size={12} className="text-blue-400" />
                        <span className="text-[#666] text-xs">Duration</span>
                      </div>
                      <span className="text-[#ccc] text-xs font-medium">{formatDuration(media.duration)}</span>
                    </div>
                  )}
                  {media.timestamp && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Calendar size={12} className="text-pink-400" />
                        <span className="text-[#666] text-xs">Date</span>
                      </div>
                      <span className="text-[#ccc] text-xs font-medium">{formatDate(media.timestamp)}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col gap-2">
                <a
                  href={api.fileUrl(media.message_id)}
                  download
                  className="flex items-center justify-center gap-2 h-10 rounded-lg bg-accent hover:bg-accent-hover text-black text-sm font-bold transition-colors"
                >
                  <Download size={15} />
                  Download File
                </a>
                <button
                  onClick={handleCopy}
                  className="flex items-center justify-center gap-2 h-10 rounded-lg bg-[#222] hover:bg-[#2a2a2a] text-[#aaa] text-sm border border-[#333] transition-colors"
                >
                  {copied ? <CheckCircle2 size={15} className="text-green-400" /> : <Copy size={15} />}
                  {copied ? 'Copied!' : 'Copy Link'}
                </button>
                <a
                  href={api.fileUrl(media.message_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 h-10 rounded-lg bg-[#222] hover:bg-[#2a2a2a] text-[#aaa] text-sm border border-[#333] transition-colors"
                >
                  <ExternalLink size={15} />
                  Open in New Tab
                </a>
              </div>

              {/* Type info */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
                <div className="flex items-center gap-3">
                  {isVideo
                    ? <Film size={20} className="text-blue-400 shrink-0" />
                    : <Image size={20} className="text-pink-400 shrink-0" />
                  }
                  <div>
                    <p className="text-white text-sm font-semibold">{isVideo ? 'Video' : 'Photo'}</p>
                    <p className="text-[#555] text-xs">{media.file_name || 'Unknown file'}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
