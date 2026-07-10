import { Film, Image, Database, Layers } from 'lucide-react'
import { useHealth } from '@/hooks/useHealth'
import { useCountUp } from '@/hooks/useCountUp'

function Stat({ icon: Icon, value, label, color }) {
  const n = useCountUp(typeof value === 'number' ? value : 0)
  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <Icon size={13} className={color} />
      <span className={`text-[13px] font-bold tabular-nums ${color}`}>
        {label ?? n.toLocaleString()}
      </span>
      <span className="text-[11px] text-[#444] hidden sm:inline">{value === null ? '' : ''}</span>
    </div>
  )
}

export default function StatsGrid() {
  const { health } = useHealth()
  const stats   = health?.stats || {}
  const total   = stats.total   ?? 0
  const videos  = stats.videos  ?? 0
  const images  = stats.images  ?? 0
  const gb      = (stats.bytes ?? 0) / (1024 ** 3)

  if (!total) return null

  return (
    <div className="flex items-center gap-3 md:gap-4 py-2.5 overflow-x-auto scrollbar-hide
                    border-b border-[#222] mb-1">
      <div className="flex items-center gap-1.5 shrink-0">
        <Layers size={13} className="text-accent" />
        <span className="text-[13px] font-bold text-accent tabular-nums">{total.toLocaleString()}</span>
        <span className="text-[11px] text-[#444]">total</span>
      </div>
      <div className="h-3 w-px bg-[#2a2a2a] shrink-0" />
      <div className="flex items-center gap-1.5 shrink-0">
        <Film size={13} className="text-blue-400" />
        <span className="text-[13px] font-bold text-blue-400 tabular-nums">{videos.toLocaleString()}</span>
        <span className="text-[11px] text-[#444]">videos</span>
      </div>
      <div className="h-3 w-px bg-[#2a2a2a] shrink-0" />
      <div className="flex items-center gap-1.5 shrink-0">
        <Image size={13} className="text-pink-400" />
        <span className="text-[13px] font-bold text-pink-400 tabular-nums">{images.toLocaleString()}</span>
        <span className="text-[11px] text-[#444]">photos</span>
      </div>
      <div className="h-3 w-px bg-[#2a2a2a] shrink-0" />
      <div className="flex items-center gap-1.5 shrink-0">
        <Database size={13} className="text-green-400" />
        <span className="text-[13px] font-bold text-green-400">{gb ? `${gb.toFixed(1)} GB` : '—'}</span>
        <span className="text-[11px] text-[#444]">storage</span>
      </div>
    </div>
  )
}
