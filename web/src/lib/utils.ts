import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let size = bytes
  let i = 0
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i += 1
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return ""
  const sec = Math.floor(seconds)
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
  }
  return `${m}:${String(s).padStart(2, "0")}`
}

export function formatRelative(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return "unknown"
  const delta = Math.floor((Date.now() - d.getTime()) / 1000)
  if (delta < 60) return "just now"
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`
  if (delta < 604800) return `${Math.floor(delta / 86400)}d ago`
  return d.toLocaleDateString()
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return "Unknown"
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function getAspectRatioClass(width: number, height: number, mediaKind: string): string {
  if (mediaKind === "video") return "aspect-video"
  
  if (!width || !height) return "aspect-square"
  
  const ratio = width / height
  
  if (ratio > 1.5) return "aspect-[4/3]"
  if (ratio > 1.1) return "aspect-video"
  if (ratio > 0.9) return "aspect-square"
  if (ratio > 0.7) return "aspect-[3/4]"
  return "aspect-[2/3]"
}
