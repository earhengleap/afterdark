import useStore from '@/store/useStore'

export default function SkeletonCard({ index = 0 }) {
  const { layout } = useStore()
  const isCompact = layout === 'compact'

  return (
    <div
      className="card-appear"
      style={{ animationDelay: `${Math.min(index * 20, 300)}ms` }}
    >
      {/* Thumbnail skeleton */}
      <div className={`${isCompact ? 'aspect-[4/3]' : 'aspect-video'} shimmer-bg`} />

      {/* Text skeleton */}
      <div className="mt-2 px-0.5 space-y-1.5">
        <div className="h-3 shimmer-bg rounded w-[85%]" />
        <div className="h-3 shimmer-bg rounded w-[60%]" />
        <div className="h-2.5 shimmer-bg rounded w-[35%]" />
      </div>
    </div>
  )
}
