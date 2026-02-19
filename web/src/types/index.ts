export interface MediaItem {
  message_id: number
  url: string
  thumb_url?: string
  media_kind: "video" | "image"
  file_name?: string
  caption?: string
  ai_title?: string
  ai_description?: string
  width?: number
  height?: number
  size?: number
  duration?: number
  date: string
  is_cached: boolean
}

export interface MediaStats {
  total: number
  videos: number
  images: number
  bytes: number
}

export type FilterType = "all" | "video" | "image"
export type SortType = "newest" | "oldest" | "largest" | "ai"
export type DensityType = "dense" | "comfort"
