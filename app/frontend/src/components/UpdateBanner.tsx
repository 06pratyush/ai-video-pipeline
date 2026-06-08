import { useEffect, useState } from 'react'
import { api, UpdateCheck } from '@/api/backend'

const DISMISSED_KEY_PREFIX = 'avs_update_dismissed_'
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000  // every 6 hours

export default function UpdateBanner() {
  const [info, setInfo] = useState<UpdateCheck | null>(null)
  const [dismissed, setDismissed] = useState(false)

  const detectPlatform = (): keyof NonNullable<UpdateCheck['downloads']> | null => {
    const ua = navigator.userAgent.toLowerCase()
    if (ua.includes('win')) return 'windows'
    if (ua.includes('mac')) return ua.includes('arm') ? 'macos_arm64' : 'macos_x64'
    if (ua.includes('linux')) return 'linux_appimage'
    return null
  }

  const checkOnce = async () => {
    try {
      const res = await api.updates.check()
      if (!res.available || !res.latest) return
      // Honor per-version dismiss
      if (localStorage.getItem(DISMISSED_KEY_PREFIX + res.latest) === 'true') {
        setDismissed(true)
        return
      }
      setInfo(res)
    } catch {}
  }

  useEffect(() => {
    checkOnce()
    const id = setInterval(checkOnce, CHECK_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  if (!info || !info.available || dismissed) return null

  const platform = detectPlatform()
  const downloadUrl = platform && info.downloads?.[platform]

  const handleDismiss = () => {
    if (info.latest) localStorage.setItem(DISMISSED_KEY_PREFIX + info.latest, 'true')
    setDismissed(true)
  }

  return (
    <div className="bg-accent/10 border-b border-accent/30 px-4 py-2 flex items-center gap-3 shrink-0">
      <span className="text-xs font-medium text-accent">↑ Update available</span>
      <span className="text-xs text-text-secondary">
        v{info.latest?.replace(/^v/, '')} — you're on v{info.current}
      </span>
      <div className="flex-1" />
      {downloadUrl && (
        <a
          href={downloadUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs px-3 py-1 rounded bg-accent text-white hover:bg-accent/90 transition-colors"
        >
          Download
        </a>
      )}
      {info.release_url && (
        <a
          href={info.release_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-text-muted hover:text-text-primary"
        >
          Release notes
        </a>
      )}
      <button
        onClick={handleDismiss}
        className="text-xs text-text-disabled hover:text-text-secondary px-1"
        title="Dismiss for this version"
      >
        ✕
      </button>
    </div>
  )
}
