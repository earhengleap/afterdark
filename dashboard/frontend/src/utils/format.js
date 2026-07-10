/**
 * Shared formatting utilities for media metadata.
 */

/** Full size string: "1.23 GB", "45.6 MB", "789 KB" */
export function formatBytes(bytes) {
  if (!bytes) return null
  const gb = bytes / 1e9
  if (gb >= 1) return `${gb.toFixed(2)} GB`
  const mb = bytes / 1e6
  if (mb >= 1) return `${mb.toFixed(1)} MB`
  return `${(bytes / 1e3).toFixed(0)} KB`
}

/** Compact size string for badges: "1.2G", "456M", "789K" */
export function formatBytesCompact(bytes) {
  if (!bytes) return null
  const mb = bytes / 1e6
  if (mb >= 1000) return `${(bytes / 1e9).toFixed(1)}G`
  if (mb >= 1) return `${mb.toFixed(0)}M`
  return `${(bytes / 1e3).toFixed(0)}K`
}

/** Duration string: "1:23:45" or "4:05" */
export function formatDuration(secs) {
  if (!secs) return null
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

/** Date string from unix timestamp: "Jan 1, 2025" */
export function formatDate(ts) {
  if (!ts) return null
  return new Date(ts * 1000).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}
