import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Users, Monitor, Smartphone, Tablet,
  Globe, Clock, ArrowLeft, Lock, Eye,
  TrendingUp, MapPin
} from 'lucide-react'
import { api } from '@/api/client'
import Spinner from '@/components/ui/Spinner'

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="stat-card flex items-center gap-4"
    >
      <div className={`p-3 rounded-xl bg-dark-elevated ${color}`}>
        <Icon size={22} />
      </div>
      <div>
        <p className="text-text-muted text-xs font-medium uppercase tracking-wider">{label}</p>
        <p className="text-text-primary text-2xl font-bold mt-0.5">{value ?? '—'}</p>
      </div>
    </motion.div>
  )
}

function DeviceBar({ label, count, total, icon: Icon, color }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <Icon size={16} className={color} />
      <span className="text-text-secondary text-sm w-16 shrink-0">{label}</span>
      <div className="flex-1 bg-dark-elevated rounded-full h-2 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
          className={`h-full rounded-full ${color.replace('text-', 'bg-')}`}
        />
      </div>
      <span className="text-text-muted text-xs w-10 text-right shrink-0">{count} ({pct}%)</span>
    </div>
  )
}
function VisitRow({ visit, index }) {
  const time = visit.ts
    ? new Date(visit.ts).toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      })
    : '—'

  const location = visit.country && visit.country !== '?' 
    ? `${visit.city && visit.city !== '?' ? visit.city + ', ' : ''}${visit.country}`
    : null

  const identifier = visit.tg_username 
    ? `@${visit.tg_username}` 
    : visit.tg_user_id 
      ? `ID: ${visit.tg_user_id}`
      : null

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      className="flex items-center gap-3 py-2.5 border-b border-dark-border/50 last:border-0"
    >
      <div className={`w-2 h-2 rounded-full shrink-0 ${visit.type === 'bot' ? 'bg-blue-400' : 'bg-accent'}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-text-secondary text-sm truncate font-medium" title={visit.page}>
            {visit.page || '/'}
          </span>
          {identifier && (
            <span className="text-accent text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent/10 border border-accent/20 uppercase tracking-tighter">
              {identifier}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 mt-0.5">
          {location && (
            <span className="flex items-center gap-1 text-text-muted text-[10px]">
              <MapPin size={10} />
              {location}
            </span>
          )}
          {visit.device_type && (
            <span className="text-text-muted text-[10px] capitalize">{visit.device_type}</span>
          )}
        </div>
      </div>
      <span className="text-text-muted text-xs shrink-0">{time}</span>
    </motion.div>
  )
}



function ReferrerRow({ referrer, count, total }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  const label = referrer || 'Direct'
  return (
    <div className="flex items-center gap-3 py-2">
      <Globe size={14} className="text-text-muted shrink-0" />
      <span className="text-text-secondary text-sm flex-1 truncate" title={label}>{label}</span>
      <div className="w-24 bg-dark-elevated rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-text-muted text-xs w-8 text-right">{count}</span>
    </div>
  )
}

export default function VisitorsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [password, setPassword] = useState(searchParams.get('password') || '')
  const [inputPw, setInputPw] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.title = 'Visitors — AfterDark'
  }, [])

  const tryFetch = async (pw) => {
    setLoading(true)
    setError('')
    try {
      const result = await api.getVisitors(pw)
      if (result.error || result.detail) throw new Error(result.error || result.detail)
      setData(result)
      setPassword(pw)
      setSearchParams({ password: pw })
    } catch (err) {
      setError(err.message || 'Invalid password or server error')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  // Auto-fetch if password in URL
  useEffect(() => {
    const pw = searchParams.get('password')
    if (pw) tryFetch(pw)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!password || error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="card p-8 w-full max-w-sm"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 rounded-xl bg-accent/20">
              <Lock size={20} className="text-accent" />
            </div>
            <div>
              <h1 className="text-text-primary font-bold text-lg">Visitor Analytics</h1>
              <p className="text-text-muted text-sm">Enter password to view</p>
            </div>
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); tryFetch(inputPw) }}
            className="flex flex-col gap-3"
          >
            <input
              type="password"
              value={inputPw}
              onChange={(e) => setInputPw(e.target.value)}
              placeholder="Password"
              autoFocus
              className="input-field w-full"
            />
            {error && (
              <p className="text-error text-sm">{error}</p>
            )}
            <button
              type="submit"
              disabled={loading || !inputPw}
              className="btn-primary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? <Spinner size="sm" /> : <Eye size={16} />}
              View Analytics
            </button>
          </form>

          <div className="mt-4 pt-4 border-t border-dark-border">
            <Link to="/" className="flex items-center gap-2 text-text-muted text-sm hover:text-text-secondary transition-colors">
              <ArrowLeft size={14} />
              Back to Gallery
            </Link>
          </div>
        </motion.div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!data) return null

  // Parse data — handle various backend shapes
  const visits = data.visitors || []
  const uniqueVisitors = data.total ?? visits.length
  const stats = data.stats || {}
  
  // Extract device counts from the backend's list format
  const deviceList = stats.devices || []
  const desktopCount = deviceList.find(d => d.type === 'Desktop')?.count || 0
  const mobileCount = deviceList.find(d => d.type === 'Mobile')?.count || 0
  const tabletCount = deviceList.find(d => d.type === 'Tablet')?.count || 0
  const totalDevices = desktopCount + mobileCount + tabletCount || 1

  // Extract referrers from the actual visit entries (since they aren't in the summary stats)
  const referrers = {}
  visits.forEach(v => {
    const ref = v.referrer || 'Direct'
    referrers[ref] = (referrers[ref] || 0) + 1
  })

  const referrerEntries = Object.entries(referrers)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
  const totalReferrals = referrerEntries.reduce((s, [, c]) => s + c, 0) || 1


  return (
    <div className="min-h-screen">
      <div className="sticky top-0 z-40 glass border-b border-dark-border">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors group">
            <ArrowLeft size={18} className="group-hover:-translate-x-0.5 transition-transform" />
            <span className="text-sm font-medium">Gallery</span>
          </Link>
          <h1 className="flex items-center gap-2 text-text-primary font-semibold">
            <TrendingUp size={16} className="text-accent" />
            Visitor Analytics
          </h1>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 md:px-6 py-6 space-y-6">
        {/* Summary cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Users} label="Unique Visitors" value={uniqueVisitors} color="text-accent" />
          <StatCard icon={Eye} label="Total Views" value={visits.length} color="text-blue-400" />
          <StatCard icon={Smartphone} label="Mobile" value={mobileCount} color="text-pink-400" />
          <StatCard icon={Monitor} label="Desktop" value={desktopCount} color="text-green-400" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Device breakdown */}
          <div className="card p-5">
            <h2 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
              <Smartphone size={16} className="text-accent" />
              Device Breakdown
            </h2>
            <div className="flex flex-col gap-3">
              <DeviceBar label="Desktop" count={desktopCount} total={totalDevices} icon={Monitor} color="text-green-400" />
              <DeviceBar label="Mobile" count={mobileCount} total={totalDevices} icon={Smartphone} color="text-pink-400" />
              <DeviceBar label="Tablet" count={tabletCount} total={totalDevices} icon={Tablet} color="text-blue-400" />
            </div>
          </div>

          {/* Top referrers */}
          <div className="card p-5">
            <h2 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
              <Globe size={16} className="text-accent" />
              Top Referrers
            </h2>
            {referrerEntries.length > 0 ? (
              <div className="flex flex-col">
                {referrerEntries.map(([ref, count]) => (
                  <ReferrerRow key={ref} referrer={ref} count={count} total={totalReferrals} />
                ))}
              </div>
            ) : (
              <p className="text-text-muted text-sm">No referrer data available</p>
            )}
          </div>
        </div>

        {/* Recent visits */}
        <div className="card p-5">
          <h2 className="text-text-primary font-semibold mb-4 flex items-center gap-2">
            <Clock size={16} className="text-accent" />
            Recent Visits
            <span className="ml-auto text-text-muted text-xs font-normal">{visits.length} total</span>
          </h2>
          {visits.length > 0 ? (
            <div className="max-h-80 overflow-y-auto scrollbar-hide">
              {visits.slice(0, 50).map((visit, i) => (
                <VisitRow key={i} visit={visit} index={i} />
              ))}
            </div>
          ) : (
            <p className="text-text-muted text-sm">No visit data available</p>
          )}
        </div>
      </div>
    </div>
  )
}
