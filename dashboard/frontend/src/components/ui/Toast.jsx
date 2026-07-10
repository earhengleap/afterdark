import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import useStore from '@/store/useStore'

const TYPE_CONFIG = {
  success: {
    icon: CheckCircle2,
    bg: 'bg-success/10 border-success/30',
    icon_color: 'text-success',
    bar: 'bg-success',
    duration: 4000,
  },
  error: {
    icon: AlertCircle,
    bg: 'bg-error/10 border-error/30',
    icon_color: 'text-error',
    bar: 'bg-error',
    duration: 8000,
  },
  warning: {
    icon: AlertTriangle,
    bg: 'bg-warning/10 border-warning/30',
    icon_color: 'text-warning',
    bar: 'bg-warning',
    duration: 5000,
  },
  info: {
    icon: Info,
    bg: 'bg-accent/10 border-accent/30',
    icon_color: 'text-accent',
    bar: 'bg-accent',
    duration: 4000,
  },
}

function ToastItem({ toast }) {
  const { removeToast } = useStore()
  const config = TYPE_CONFIG[toast.type] || TYPE_CONFIG.info
  const Icon = config.icon

  useEffect(() => {
    const timer = setTimeout(() => removeToast(toast.id), config.duration)
    return () => clearTimeout(timer)
  }, [toast.id, config.duration, removeToast])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 80, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.9 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className={`relative flex items-start gap-3 w-[340px] max-w-[calc(100vw-32px)]
                 rounded-xl border px-4 py-3 overflow-hidden
                 glass ${config.bg} shadow-card`}
    >
      <Icon size={16} className={`${config.icon_color} shrink-0 mt-0.5`} />
      <p className="flex-1 text-text-primary text-sm leading-snug">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 text-text-muted hover:text-text-secondary transition-colors -mr-1 -mt-0.5 p-1"
      >
        <X size={13} />
      </button>

      {/* Progress bar */}
      <motion.div
        className={`absolute bottom-0 left-0 h-[2px] ${config.bar} opacity-60`}
        initial={{ width: '100%' }}
        animate={{ width: '0%' }}
        transition={{ duration: config.duration / 1000, ease: 'linear' }}
      />
    </motion.div>
  )
}

export default function Toast() {
  const { toasts } = useStore()

  return (
    <div className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 items-end pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  )
}
