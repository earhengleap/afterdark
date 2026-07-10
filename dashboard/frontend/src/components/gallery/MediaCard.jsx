import { useState, useRef, useCallback } from 'react'
import { Play, Download, Image as ImageIcon, Zap } from 'lucide-react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'
import { formatBytesCompact, formatDuration } from '@/utils/format'

const DAY_MS = 86_400_000

export default function MediaCard({ item, index, onClick }) {
  const { layout } = useStore()
  const isCompact = layout === 'compact'

  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError]   = useState(false)

  const isVideo = item.file_type === 'video' || item.media_kind === 'video'
  const title   = item.ai_title || item.caption || item.file_name || 'Untitled'
  const duration = formatDuration(item.duration)
  const size     = formatBytesCompact(item.file_size)

  const quality = !item.width ? null
    : item.width >= 3840 ? '4K'
    : item.width >= 1920 ? 'FHD'
    : (item.width >= 1280 || item.height >= 720) ? 'HD'
    : null

  // "NEW" badge — within 3 days
  const isNew = item.timestamp && (Date.now() - item.timestamp * 1000) < 3 * DAY_MS

  // First 8 cards are above the fold — load them eagerly for fast LCP
  const eager = index < 8

  return (
    <div
      className="media-card card-appear group cursor-pointer"
      style={{ animationDelay: `${Math.min(index * 10, 180)}ms` }}
      onClick={onClick}
    >
      {/* ── Thumbnail ── */}
      <div className={`relative overflow-hidden bg-[#1c1c1c] rounded-sm
                      ${isCompact ? 'aspect-[4/3]' : 'aspect-video'}
                      outline outline-2 outline-transparent
                      group-hover:outline-accent/70
                      transition-[outline-color] duration-150`}>

        {/* Shimmer — hidden once image loaded */}
        {!imgLoaded && !imgError && (
          <div className="absolute inset-0 shimmer-bg" />
        )}

        {/* Thumbnail image */}
        {!imgError && (
          <img
            src={api.thumbUrl(item.message_id)}
            alt={title}
            loading={eager ? 'eager' : 'lazy'}
            decoding="async"
            fetchpriority={index < 4 ? 'high' : 'auto'}
            onLoad={() => setImgLoaded(true)}
            onError={(e) => {
              if (!isVideo && e.target.src !== api.fileUrl(item.message_id)) {
                e.target.src = api.fileUrl(item.message_id)
              } else {
                setImgError(true)
                setImgLoaded(true)
              }
            }}
            className={`absolute inset-0 w-full h-full object-cover will-change-transform
                       transition-[opacity,transform] duration-150 ease-out
                       ${imgLoaded ? 'opacity-100' : 'opacity-0'}
                       group-hover:scale-[1.05]`}
          />
        )}

        {/* Error fallback */}
        {imgError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#1c1c1c]">
            {isVideo
              ? <Play size={24} className="text-[#333]" />
              : <ImageIcon size={24} className="text-[#333]" />
            }
            <span className="text-[10px] text-[#444]">No Preview</span>
          </div>
        )}

        {/* Bottom gradient — readability for badges */}
        <div className="absolute inset-x-0 bottom-0 h-20
                       bg-gradient-to-t from-black/95 via-black/50 to-transparent
                       pointer-events-none" />

        {/* ── Quality badge — bottom left ── */}
        {quality && (
          <span className={`absolute bottom-[7px] left-[6px] z-10 leading-none
                          text-[10px] font-black px-[5px] py-[3px] rounded-[3px]
                          ${quality === '4K'
                            ? 'bg-[#ffd000] text-black'
                            : quality === 'FHD'
                              ? 'bg-blue-600 text-white'
                              : 'bg-[#2db400] text-white'}`}>
            {quality}
          </span>
        )}

        {/* ── Duration — bottom right ── */}
        {duration && (
          <span className="absolute bottom-[7px] right-[6px] z-10 leading-none
                          text-[11px] font-semibold bg-black/88 text-white
                          px-[5px] py-[3px] rounded-[3px]">
            {duration}
          </span>
        )}

        {/* ── NEW badge — top left ── */}
        {isNew && (
          <span className="absolute top-[6px] left-[6px] z-10 leading-none
                          text-[9px] font-black px-[5px] py-[3px] rounded-[3px]
                          bg-white text-black flex items-center gap-0.5">
            <Zap size={8} />NEW
          </span>
        )}

        {/* ── Minimalist play button — center on hover ── */}
        {isVideo && (
          <div className="absolute inset-0 flex items-center justify-center z-10
                         opacity-0 group-hover:opacity-100 transition-opacity duration-150">
            <div className="w-11 h-11 rounded-full bg-white/90 backdrop-blur-md flex items-center justify-center
                           shadow-[0_0_24px_rgba(255,255,255,0.4)]
                           scale-90 group-hover:scale-100 transition-transform duration-150">
              <Play size={18} fill="black" className="text-black ml-1" />
            </div>
          </div>
        )}

        {/* ── Download — top right on hover ── */}
        <a
          href={api.fileUrl(item.message_id)}
          download
          onClick={(e) => e.stopPropagation()}
          title="Download"
          className="absolute top-[6px] right-[6px] z-20
                     opacity-0 group-hover:opacity-100 transition-opacity duration-150
                     w-7 h-7 flex items-center justify-center rounded-[3px]
                     bg-black/80 border border-white/10
                     hover:bg-accent hover:border-accent"
        >
          <Download size={11} className="text-white" />
        </a>
      </div>

      {/* ── Info ── */}
      <div className="mt-1.5 px-0.5">
        <p className={`font-medium leading-snug line-clamp-2
                      text-[#ccc] group-hover:text-accent transition-colors duration-150
                      ${isCompact ? 'text-[11px]' : 'text-[13px]'}`}>
          {title}
        </p>
        {size && (
          <p className="mt-0.5 text-[11px] text-[#444]">{size}</p>
        )}
      </div>
    </div>
  )
}
