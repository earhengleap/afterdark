import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, X, Send, Bot, User, Maximize2 } from 'lucide-react'
import { api } from '@/api/client'
import useStore from '@/store/useStore'

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-3 py-2">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-text-muted"
          animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  const time = new Date(msg.ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-end gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mb-0.5
                      ${isUser ? 'bg-accent' : 'bg-dark-elevated border border-dark-border'}`}>
        {isUser ? <User size={12} className="text-white" /> : <Bot size={12} className="text-accent" />}
      </div>
      <div className={`max-w-[80%] flex flex-col gap-0.5 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-3 py-2 rounded-2xl text-sm leading-relaxed
                        ${isUser
                          ? 'bg-accent text-white rounded-br-sm'
                          : 'bg-dark-elevated border border-dark-border text-text-primary rounded-bl-sm'
                        }`}>
          {msg.content}
        </div>
        <span className="text-text-muted text-2xs px-1">{time}</span>
      </div>
    </motion.div>
  )
}

const DRAG_SNAP_MARGIN = 12

export default function ChatWidget() {
  const { addToast } = useStore()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [mobile, setMobile] = useState(window.innerWidth < 640)

  // FAB drag position
  const [fabPos, setFabPos] = useState({ x: 0, y: 0 })
  const dragging = useRef(false)
  const dragOffset = useRef({ x: 0, y: 0 })
  const fabRef = useRef(null)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth < 640)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150)
  }, [open])

  const pollForResult = useCallback(async (taskId) => {
    let attempts = 0
    const poll = async () => {
      try {
        const result = await api.chatResult(taskId)
        if (result.status === 'done' && result.reply) {
          setMessages((prev) => [...prev, { role: 'assistant', content: result.reply, ts: Date.now() }])
          setLoading(false)
          return
        }
        attempts++
        if (attempts < 30) {
          pollRef.current = setTimeout(poll, 2000)
        } else {
          setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, the request timed out. Please try again.', ts: Date.now() }])
          setLoading(false)
        }
      } catch {
        setMessages((prev) => [...prev, { role: 'assistant', content: 'Connection error. Please try again.', ts: Date.now() }])
        setLoading(false)
      }
    }
    poll()
  }, [])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text, ts: Date.now() }])
    setLoading(true)

    try {
      const result = await api.chat(text)
      if (result.task_id) {
        pollForResult(result.task_id)
      } else if (result.reply) {
        setMessages((prev) => [...prev, { role: 'assistant', content: result.reply, ts: Date.now() }])
        setLoading(false)
      } else {
        throw new Error('No task_id returned')
      }
    } catch (err) {
      addToast('Chat error: ' + (err.message || 'Unknown'), 'error')
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Failed to send. Please try again.', ts: Date.now() }])
      setLoading(false)
    }
  }, [input, loading, pollForResult, addToast])

  useEffect(() => () => clearTimeout(pollRef.current), [])

  // FAB drag handlers
  const handleFabMouseDown = (e) => {
    if (e.button !== 0) return
    e.preventDefault()
    const rect = fabRef.current.getBoundingClientRect()
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top }
    dragging.current = true

    const onMove = (e2) => {
      if (!dragging.current) return
      const newX = e2.clientX - dragOffset.current.x - (window.innerWidth - 88)
      const newY = e2.clientY - dragOffset.current.y - (window.innerHeight - 88)
      setFabPos({ x: newX, y: newY })
    }
    const onUp = () => {
      dragging.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <>
      {/* FAB */}
      <AnimatePresence>
        {!open && (
          <motion.button
            ref={fabRef}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            className="fixed z-50 w-14 h-14 rounded-full
                       bg-gradient-to-br from-accent to-pink-500
                       flex items-center justify-center
                       shadow-glow-lg animate-pulseGlow
                       cursor-grab active:cursor-grabbing
                       no-tap-highlight"
            style={{
              bottom: `${24 - fabPos.y}px`,
              right: `${24 - fabPos.x}px`,
            }}
            onClick={() => setOpen(true)}
            onMouseDown={handleFabMouseDown}
          >
            <Sparkles size={22} className="text-white" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85, y: 40 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: 40 }}
            transition={{ type: 'spring', stiffness: 350, damping: 30 }}
            className={`fixed z-50 flex flex-col overflow-hidden
                       glass-elevated border border-dark-border shadow-glow-lg
                       ${mobile
                          ? 'inset-0 rounded-none'
                          : 'bottom-6 right-6 w-[380px] h-[520px] rounded-2xl'
                       }`}
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-dark-border bg-dark-elevated/50">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent to-pink-500 flex items-center justify-center">
                <Sparkles size={14} className="text-white" />
              </div>
              <span className="text-text-primary font-semibold text-sm">AI Assistant</span>
              <div className="ml-auto flex items-center gap-1">
                {!mobile && (
                  <button
                    onClick={() => setMobile(true)}
                    className="btn-icon p-1.5"
                    title="Expand"
                  >
                    <Maximize2 size={13} />
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="btn-icon p-1.5"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 scrollbar-hide">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent/20 to-pink-500/20 flex items-center justify-center border border-accent/20">
                    <Bot size={24} className="text-accent" />
                  </div>
                  <div>
                    <p className="text-text-primary font-medium text-sm">How can I help?</p>
                    <p className="text-text-muted text-xs mt-1">Ask about your media collection</p>
                  </div>
                  {["What's in my gallery?", 'Show me recent videos', 'Help me organize'].map((hint) => (
                    <button
                      key={hint}
                      onClick={() => { setInput(hint); inputRef.current?.focus() }}
                      className="text-xs text-text-muted border border-dark-border rounded-xl px-3 py-1.5
                                 hover:border-accent/40 hover:text-text-secondary transition-all duration-150"
                    >
                      {hint}
                    </button>
                  ))}
                </div>
              )}
              {messages.map((msg, i) => <Message key={i} msg={msg} />)}
              {loading && (
                <div className="flex items-end gap-2">
                  <div className="w-6 h-6 rounded-full bg-dark-elevated border border-dark-border flex items-center justify-center shrink-0">
                    <Bot size={12} className="text-accent" />
                  </div>
                  <div className="bg-dark-elevated border border-dark-border rounded-2xl rounded-bl-sm">
                    <TypingDots />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-3 border-t border-dark-border bg-dark-elevated/30">
              <div className="flex items-center gap-2 bg-dark-elevated rounded-xl border border-dark-border focus-within:border-accent/40 transition-colors">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                  placeholder="Ask about your gallery…"
                  className="flex-1 bg-transparent px-3.5 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none"
                  disabled={loading}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || loading}
                  className="w-8 h-8 rounded-lg bg-accent hover:bg-accent-hover flex items-center justify-center
                             shrink-0 mr-1.5 transition-all duration-200 active:scale-90
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Send size={14} className="text-white" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
