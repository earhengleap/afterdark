import { ChevronDown, Grid3X3, LayoutGrid } from 'lucide-react'
import useStore from '@/store/useStore'

const FILTERS = [
  { value: 'all',   label: 'All' },
  { value: 'video', label: 'Videos' },
  { value: 'image', label: 'Photos' },
]

const SORTS = [
  { value: 'newest',  label: 'Newest' },
  { value: 'oldest',  label: 'Oldest' },
  { value: 'largest', label: 'Largest' },
  { value: 'ai',      label: 'AI Enhanced' },
]

export default function FilterBar() {
  const {
    filter, setFilter,
    sort, setSort,
    layout, setLayout,
    items, totalCount,
    health,
  } = useStore()

  const videosCount = health?.total_videos ?? null
  const imagesCount = health?.total_images ?? null

  const getCount = (f) => {
    if (f === 'video') return videosCount
    if (f === 'image') return imagesCount
    return totalCount || null
  }

  return (
    <div className="flex items-center gap-2 md:gap-3 py-3 mb-2
                    border-b border-[#2a2a2a] overflow-x-auto scrollbar-hide">

      {/* ── Filter tabs ─ PH underline style ── */}
      <div className="flex items-center gap-0 shrink-0">
        {FILTERS.map((f) => {
          const count = getCount(f.value)
          const active = filter === f.value
          return (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`relative px-4 py-2 text-[13px] font-semibold whitespace-nowrap
                         transition-colors duration-150 no-tap-highlight
                         ${active ? 'text-white' : 'text-[#777] hover:text-[#bbb]'}`}
            >
              {f.label}
              {count !== null && (
                <span className={`ml-1.5 text-[11px] font-bold
                                 ${active ? 'text-[#aaa]' : 'text-[#555]'}`}>
                  {count.toLocaleString()}
                </span>
              )}
              {/* Active underline */}
              {active && (
                <span className="absolute bottom-0 inset-x-2 h-[2px] bg-accent rounded-full" />
              )}
            </button>
          )
        })}
      </div>

      {/* Spacer */}
      <div className="flex-1 min-w-4" />

      {/* ── Item count ── */}
      <span className="text-[#444] text-xs hidden sm:block shrink-0 whitespace-nowrap">
        {items.length.toLocaleString()}
        {totalCount > 0 && ` / ${totalCount.toLocaleString()}`}
      </span>

      {/* ── Sort dropdown ── */}
      <div className="relative shrink-0">
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="appearance-none h-8 bg-[#222] border border-[#333] text-[#aaa]
                     text-[12px] font-medium rounded-lg pl-3 pr-7 cursor-pointer
                     hover:border-[#444] focus:outline-none focus:border-accent/50
                     transition-colors duration-150"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value} className="bg-[#1a1a1a]">
              {s.label}
            </option>
          ))}
        </select>
        <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#555] pointer-events-none" />
      </div>

      {/* ── Layout toggle ── */}
      <div className="flex items-center gap-px bg-[#222] rounded-lg p-1 border border-[#333] shrink-0">
        {[
          { value: 'spacious', icon: Grid3X3,   title: 'Spacious' },
          { value: 'compact',  icon: LayoutGrid, title: 'Compact'  },
        ].map(({ value, icon: Icon, title }) => (
          <button
            key={value}
            onClick={() => setLayout(value)}
            title={title}
            className={`p-1.5 rounded transition-all duration-150 no-tap-highlight
              ${layout === value
                ? 'bg-accent text-black'
                : 'text-[#555] hover:text-[#999]'}`}
          >
            <Icon size={13} />
          </button>
        ))}
      </div>
    </div>
  )
}
