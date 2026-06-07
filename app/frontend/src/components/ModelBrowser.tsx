import { useState, useEffect } from 'react'
import { api, ModelInfo, CatalogModel, VramStatus } from '@/api/backend'
import { useModelStore } from '@/stores/modelStore'

const TYPE_LABEL: Record<string, string> = {
  llm: 'LLM', video: 'Video', tts: 'Voice', transcriber: 'Subtitles',
  music: 'Music', upscaler: 'Upscaler', interpolator: 'Interpolation',
}
const TIER_COLOR: Record<string, string> = {
  fast: 'text-success', balanced: 'text-warning', premium: 'text-accent',
}

export default function ModelBrowser({ onClose }: { onClose: () => void }) {
  const { models, fetchAll } = useModelStore()
  const [catalog, setCatalog]   = useState<CatalogModel[]>([])
  const [vram, setVram]         = useState<VramStatus | null>(null)
  const [pulling, setPulling]   = useState<string | null>(null)
  const [cacheStats, setCacheStats] = useState<{ total_entries: number; entries_with_hits: number } | null>(null)
  const [tab, setTab]           = useState<'installed' | 'available'>('installed')

  useEffect(() => {
    api.models.catalog().then((c) => setCatalog(c.models)).catch(() => {})
    api.system.vram().then(setVram).catch(() => {})
    api.system.cacheStats().then(setCacheStats).catch(() => {})
  }, [])

  const handleInstallOllama = async (model: CatalogModel) => {
    setPulling(model.id)
    try {
      await api.models.installOllama(model.id)
      // Poll refresh after a delay to pick up the installed model
      setTimeout(() => { fetchAll(); setPulling(null) }, 5000)
    } catch {
      setPulling(null)
    }
  }

  const handleClearCache = async () => {
    await api.system.clearCache()
    const stats = await api.system.cacheStats()
    setCacheStats(stats)
  }

  const installedIds = new Set(models.map((m) => {
    // Map registry id like "ollama:gemma3:4b" back to catalog id
    if (m.source === 'ollama') return 'gemma3-4b'  // rough match
    return m.id.replace('comfyui:', '').replace('kokoro:', '')
  }))

  const grouped = models.reduce<Record<string, ModelInfo[]>>((acc, m) => {
    const t = m.type
    acc[t] = acc[t] ? [...acc[t], m] : [m]
    return acc
  }, {})

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6">
      <div className="bg-bg-surface border border-border-base rounded-card w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Model Browser</h2>
            {vram && (
              <div className="flex items-center gap-2 mt-1">
                <div className="w-24 h-1.5 bg-bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full transition-all"
                    style={{ width: `${vram.pct_used}%` }}
                  />
                </div>
                <span className="text-xs text-text-muted">
                  {Math.round(vram.used_mb / 1024 * 10) / 10}GB / {Math.round(vram.total_mb / 1024 * 10) / 10}GB VRAM
                </span>
              </div>
            )}
          </div>
          <button className="text-text-muted hover:text-text-primary text-lg leading-none" onClick={onClose}>✕</button>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b border-border-subtle shrink-0">
          {(['installed', 'available'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2.5 text-sm capitalize transition-colors border-b-2
                ${tab === t
                  ? 'border-accent text-text-primary font-medium'
                  : 'border-transparent text-text-muted hover:text-text-secondary'}`}
            >
              {t === 'installed' ? `Installed (${models.length})` : 'Available'}
            </button>
          ))}
          <div className="flex-1" />
          <button
            className="px-4 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
            onClick={() => fetchAll()}
          >
            ↺ Refresh
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">

          {tab === 'installed' && (
            <>
              {Object.keys(grouped).length === 0 && (
                <p className="text-sm text-text-disabled text-center mt-10">
                  No models detected. Make sure Ollama is running and ComfyUI is configured.
                </p>
              )}
              {Object.entries(grouped).map(([type, items]) => (
                <div key={type}>
                  <div className="text-xs font-medium text-text-disabled uppercase tracking-wider mb-2">
                    {TYPE_LABEL[type] ?? type}
                  </div>
                  <div className="space-y-1">
                    {items.map((m) => (
                      <div key={m.id} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-bg-raised border border-border-subtle">
                        <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-text-primary truncate">{m.name}</div>
                          <div className="text-xs text-text-muted truncate">{m.description}</div>
                        </div>
                        {m.size_mb > 0 && (
                          <span className="text-xs text-text-disabled shrink-0">
                            {m.size_mb > 1024 ? `${(m.size_mb / 1024).toFixed(1)}GB` : `${m.size_mb}MB`}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* Cache stats */}
              {cacheStats && (
                <div className="border border-border-subtle rounded-lg p-3 mt-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-medium text-text-secondary mb-0.5">Generation Cache</div>
                      <div className="text-xs text-text-muted">
                        {cacheStats.total_entries} entries · {cacheStats.entries_with_hits} with cache hits
                      </div>
                    </div>
                    <button
                      className="text-xs text-error/70 hover:text-error transition-colors"
                      onClick={handleClearCache}
                    >
                      Clear
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {tab === 'available' && (
            <div className="space-y-2">
              {catalog.map((m) => (
                <div key={m.id} className="flex items-start gap-3 px-3 py-3 rounded-lg bg-bg-raised border border-border-subtle">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-medium text-text-primary">{m.name}</span>
                      <span className={`text-xs ${TIER_COLOR[m.quality_tier] ?? 'text-text-muted'}`}>
                        {m.quality_tier}
                      </span>
                      <span className="text-xs text-text-disabled">{TYPE_LABEL[m.type] ?? m.type}</span>
                    </div>
                    <p className="text-xs text-text-muted mb-1.5">{m.description}</p>
                    <div className="flex gap-3 text-xs text-text-disabled">
                      <span>{m.size_gb}GB</span>
                      <span>{Math.round(m.vram_required_mb / 1024)}GB VRAM</span>
                      <span>{m.install_method}</span>
                    </div>
                  </div>
                  <div className="shrink-0">
                    {m.install_method === 'ollama' ? (
                      <button
                        className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50"
                        disabled={pulling === m.id}
                        onClick={() => handleInstallOllama(m)}
                      >
                        {pulling === m.id ? 'Pulling…' : '↓ Install'}
                      </button>
                    ) : m.install_method === 'huggingface' ? (
                      <span className="text-xs text-text-disabled px-3 py-1.5 border border-border-subtle rounded">
                        Via bootstrap
                      </span>
                    ) : (
                      <span className="text-xs text-text-disabled px-3 py-1.5 border border-border-subtle rounded">
                        pip install
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
