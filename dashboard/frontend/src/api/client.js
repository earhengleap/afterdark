export const api = {
  getMedia: ({ limit = 50, offset = 0, filter = 'all', sort = 'newest', search = '', signal } = {}) =>
    fetch(
      `/api/media?limit=${limit}&offset=${offset}&filter=${filter}&sort=${sort}&search=${encodeURIComponent(search)}`,
      { signal }
    ).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    }),

  getMediaById: (id) =>
    fetch(`/api/media/${id}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(payload => {
        if (payload && typeof payload === 'object' && payload.item) {
          return payload.item
        }
        return payload
      }),

  getHealth: () =>
    fetch('/api/health')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),

  sync: (limit = 'all') =>
    fetch(`/api/sync?limit=${limit}`, { method: 'POST' })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),

  aiTitles: (batchSize = 25) =>
    fetch(`/api/ai-titles?batch_size=${batchSize}`, { method: 'POST' })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),

  chat: (message) =>
    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    }),

  chatResult: (taskId) =>
    fetch(`/api/chat/result/${taskId}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),

  getVisitors: (password) =>
    fetch(`/api/visitors?password=${encodeURIComponent(password)}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),

  track: (data) =>
    fetch('/api/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).catch(() => {}),

  thumbUrl: (id) => `/api/thumb/${id}`,
  fileUrl: (id) => `/api/file/${id}`,
}
