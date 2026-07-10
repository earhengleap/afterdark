import { create } from 'zustand'

let toastIdCounter = 0

const useStore = create((set, get) => ({
  // Data
  items: [],
  totalCount: 0,
  hasMore: true,
  loading: false,
  syncing: false,
  generatingAI: false,
  health: null,

  // Filters
  filter: 'all',
  sort: 'newest',
  search: '',
  layout: 'spacious',

  // Viewer
  viewerOpen: false,
  viewerIndex: -1,

  // Toast
  toasts: [],

  // --- Data actions ---
  setItems: (items, totalCount) =>
    set({ items, totalCount, hasMore: items.length < totalCount }),

  appendItems: (newItems) =>
    set((state) => {
      const merged = [...state.items, ...newItems]
      return { items: merged, hasMore: merged.length < state.totalCount }
    }),

  setLoading: (loading) => set({ loading }),
  setSyncing: (syncing) => set({ syncing }),
  setGeneratingAI: (generatingAI) => set({ generatingAI }),
  setHealth: (health) => set({ health }),
  setTotalCount: (totalCount) => set({ totalCount }),

  // --- Filter actions ---
  setFilter: (filter) => set({ filter, items: [], hasMore: true }),
  setSort: (sort) => set({ sort, items: [], hasMore: true }),
  setSearch: (search) => set({ search, items: [], hasMore: true }),
  setLayout: (layout) => set({ layout }),

  // --- Viewer actions ---
  openViewer: (index) => set({ viewerOpen: true, viewerIndex: index }),
  closeViewer: () => set({ viewerOpen: false, viewerIndex: -1 }),
  nextItem: () => {
    const { viewerIndex, items } = get()
    if (viewerIndex < items.length - 1) {
      set({ viewerIndex: viewerIndex + 1 })
    }
  },
  prevItem: () => {
    const { viewerIndex } = get()
    if (viewerIndex > 0) {
      set({ viewerIndex: viewerIndex - 1 })
    }
  },

  // --- Toast actions ---
  addToast: (message, type = 'info') => {
    const id = ++toastIdCounter
    set((state) => ({
      toasts: [...state.toasts, { id, message, type, createdAt: Date.now() }],
    }))
    return id
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}))

export default useStore
