import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import GalleryPage from '@/pages/GalleryPage'
import VisitorsPage from '@/pages/VisitorsPage'
import Toast from '@/components/ui/Toast'

export default function App() {
  useEffect(() => {
    // Initialize Telegram Mini App if loaded inside Telegram
    if (window.Telegram && window.Telegram.WebApp) {
      try {
        const tg = window.Telegram.WebApp
        tg.ready()     // Tell Telegram the app is fully loaded
        tg.expand()    // Expand to full height automatically

        // Match app background to Telegram theme
        document.documentElement.style.setProperty('--tg-theme-bg-color', tg.backgroundColor || '#111111')
      } catch (e) {
        console.warn('Telegram WebApp init failed:', e)
      }
    }
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        {/* Both gallery and /view/:id render GalleryPage so the modal
            opens instantly without a full page reload or extra API call */}
        <Route path="/" element={<GalleryPage />} />
        <Route path="/view/:id" element={<GalleryPage />} />
        <Route path="/visitors" element={<VisitorsPage />} />
      </Routes>
      <Toast />
    </BrowserRouter>
  )
}
