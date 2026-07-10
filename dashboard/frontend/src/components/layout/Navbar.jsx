import { useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Search, X, RefreshCw, Sparkles, Users, AlertTriangle
} from 'lucide-react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'

export default function Navbar() {
  const {
    search, setSearch,
    syncing, setSyncing,
    generatingAI, setGeneratingAI,
    totalCount,
    health,
    addToast,
  } = useStore()

  const isBotMode = health?.session_mode === 'bot'
  const syncError = health?.last_sync_error || null

  const [localSearch, setLocalSearch] = useState(search)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  const handleSearchChange = useCallback((val) => {
    setLocalSearch(val)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setSearch(val), 400)
  }, [setSearch])

  const clearSearch = () => {
    setLocalSearch('')
    setSearch('')
    searchRef.current?.focus()
  }

  const submitSearch = () => {
    clearTimeout(debounceRef.current)
    setSearch(localSearch)
  }

  const handleSync = async () => {
    if (syncing) return
    setSyncing(true)
    try {
      const result = await api.sync()
      const total = result.total ?? result.total_count ?? null
      const newItems = result.new_items ?? result.synced ?? result.count ?? 0
      const msg = total !== null
        ? `Synced — ${total.toLocaleString()} total`
        : `Synced ${newItems} new item${newItems !== 1 ? 's' : ''}`
      addToast(msg, newItems > 0 || total ? 'success' : 'info')
    } catch (err) {
      addToast('Sync failed: ' + (err.message || 'Unknown error'), 'error')
    } finally {
      setSyncing(false)
    }
  }

  const handleAI = async () => {
    if (generatingAI) return
    setGeneratingAI(true)
    try {
      const result = await api.aiTitles(25)
      const generated = result.generated ?? result.count ?? result.updated ?? 0
      addToast(`AI titles generated for ${generated} item${generated !== 1 ? 's' : ''}`, 'success')
    } catch (err) {
      addToast('AI generation failed: ' + (err.message || 'Unknown error'), 'error')
    } finally {
      setGeneratingAI(false)
    }
  }

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-[60px] bg-[#1b1b1b] border-b border-[#2a2a2a]">
      <div className="max-w-[1920px] mx-auto px-3 md:px-5 h-full flex items-center gap-3 md:gap-5">

        {/* ── Logo ── PH-style: word + coloured block ── */}
        <AnimatePresence>
          {!mobileSearchOpen && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="shrink-0"
            >
              <Link to="/" className="flex items-center no-tap-highlight select-none">
                <span className="font-black text-[22px] text-white leading-none tracking-tight">
                  After
                </span>
                <span className="ml-1 font-black text-[20px] px-[7px] py-[2px]
                                bg-accent text-black rounded leading-snug tracking-tight">
                  Dark
                </span>
              </Link>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Search bar ── Desktop: always visible, Mobile: toggle ── */}
        <div className={`flex-1 ${mobileSearchOpen ? '' : 'hidden md:flex'} md:flex max-w-2xl`}>
          {/* Input + search button joined */}
          <div className="flex w-full">
            <div className="relative flex-1">
              <input
                ref={searchRef}
                type="text"
                value={localSearch}
                onChange={(e) => handleSearchChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submitSearch()}
                placeholder="Search videos, images..."
                className="w-full h-9 bg-[#2b2b2b] border border-[#3d3d3d] border-r-0
                           rounded-l-full pl-4 pr-8 text-[13px] text-white placeholder-[#555]
                           focus:outline-none focus:border-accent/60
                           transition-colors duration-150"
              />
              {localSearch && (
                <button
                  onClick={clearSearch}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors"
                >
                  <X size={13} />
                </button>
              )}
            </div>
            <button
              onClick={submitSearch}
              className="h-9 px-4 bg-accent hover:bg-accent-hover
                         border border-accent rounded-r-full
                         flex items-center justify-center
                         transition-colors duration-150 shrink-0"
            >
              <Search size={16} className="text-black" />
            </button>
          </div>
        </div>

        {/* Mobile: search toggle */}
        {!mobileSearchOpen && (
          <button
            className="md:hidden btn-icon"
            onClick={() => { setMobileSearchOpen(true); setTimeout(() => searchRef.current?.focus(), 80) }}
          >
            <Search size={18} />
          </button>
        )}
        {mobileSearchOpen && (
          <button className="md:hidden btn-icon" onClick={() => { setMobileSearchOpen(false); clearSearch() }}>
            <X size={18} />
          </button>
        )}

        {/* ── Right controls ── */}
        {!mobileSearchOpen && (
          <div className="flex items-center gap-1.5 shrink-0 ml-auto">

            {/* Item count */}
            {totalCount > 0 && (
              <span className="hidden lg:block text-[#555] text-xs font-medium px-3 py-1.5
                               bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg">
                {totalCount.toLocaleString()} items
              </span>
            )}

            {/* Sync */}
            <div className="relative">
              <button
                onClick={handleSync}
                disabled={syncing}
                className="btn-icon disabled:opacity-50 no-tap-highlight"
                title={isBotMode ? 'Bot mode — set SESSION_STRING for full sync' : syncError ? `Sync error: ${syncError}` : 'Sync from Telegram'}
              >
                <RefreshCw size={16} className={syncing ? 'animate-spin text-accent' : 'text-[#888]'} />
              </button>
              {(isBotMode || syncError) && !syncing && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-yellow-400 border border-[#1b1b1b]" />
              )}
            </div>

            {/* Bot mode chip */}
            {isBotMode && (
              <div className="hidden lg:flex items-center gap-1 px-2 py-1 rounded-lg
                             bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-medium">
                <AlertTriangle size={11} />
                <span>Bot mode</span>
              </div>
            )}

            {/* AI titles */}
            <button
              onClick={handleAI}
              disabled={generatingAI}
              className="flex items-center gap-1.5 h-8 px-3 rounded-lg
                         bg-accent hover:bg-accent-hover text-black text-xs font-bold
                         transition-colors duration-150 active:scale-95
                         disabled:opacity-50 disabled:cursor-not-allowed no-tap-highlight"
              title="Generate AI Titles"
            >
              <Sparkles size={13} className={generatingAI ? 'animate-pulse' : ''} />
              <span className="hidden sm:inline">{generatingAI ? 'Working…' : 'AI Titles'}</span>
            </button>

            {/* Visitors */}
            <Link to="/visitors" className="btn-icon" title="Analytics">
              <Users size={16} className="text-[#888]" />
            </Link>
          </div>
        )}
      </div>
    </header>
  )
}
