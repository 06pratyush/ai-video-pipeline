import { useEffect, useState } from 'react'
import { api, LongFormPreview, RenderOpts } from '@/api/backend'
import { useProjectStore } from '@/stores/projectStore'
import { useModelStore } from '@/stores/modelStore'

const VOICES = [
  'af_sarah', 'af_bella', 'af_heart', 'af_nicole',
  'am_adam', 'am_michael', 'bf_emma', 'bm_george',
]

export default function LongFormModal({ onClose }: { onClose: () => void }) {
  const { fetchProjects } = useProjectStore()
  const { skills } = useModelStore()

  const [baseName, setBaseName]       = useState('')
  const [topic, setTopic]             = useState('')
  const [script, setScript]           = useState('')
  const [voice, setVoice]             = useState('af_sarah')
  const [skillId, setSkillId]         = useState<string>('')
  const [chunkWords, setChunkWords]   = useState(180)
  const [preview, setPreview]         = useState<LongFormPreview | null>(null)
  const [opts, setOpts]               = useState<RenderOpts>({
    subtitles: false, music: false, interpolation: false, upscaling: false,
  })
  const [submitting, setSubmitting]   = useState(false)
  const [error, setError]             = useState('')

  // Debounced preview
  useEffect(() => {
    if (!script.trim()) { setPreview(null); return }
    const t = setTimeout(() => {
      api.longform.preview(script, chunkWords)
        .then(setPreview)
        .catch(() => setPreview(null))
    }, 400)
    return () => clearTimeout(t)
  }, [script, chunkWords])

  const toggle = (key: keyof RenderOpts) =>
    setOpts((o) => ({ ...o, [key]: !o[key] }))

  const handleSubmit = async () => {
    if (!baseName.trim() || !topic.trim() || !script.trim()) {
      setError('Name, topic, and script are required.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      await api.longform.create({
        base_name:  baseName.trim(),
        topic:      topic.trim().replace(/\s+/g, '-').toLowerCase(),
        script:     script.trim(),
        voice,
        skill_id:   skillId || null,
        chunk_words: chunkWords,
        render_opts: opts,
      })
      await fetchProjects()
      onClose()
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6">
      <div className="bg-bg-surface border border-border-base rounded-card w-full max-w-3xl max-h-[88vh] flex flex-col shadow-2xl">

        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Long-form Mode</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Split a long script into multiple sub-projects rendered in sequence
            </p>
          </div>
          <button className="text-text-muted hover:text-text-primary text-lg" onClick={onClose}>✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-text-secondary block mb-1">Base name</label>
              <input
                className="input text-sm"
                placeholder="My long-form series"
                value={baseName}
                onChange={(e) => setBaseName(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-text-secondary block mb-1">Topic slug</label>
              <input
                className="input text-sm"
                placeholder="my-series"
                value={topic}
                onChange={(e) => setTopic(e.target.value.replace(/\s+/g, '-').toLowerCase())}
              />
            </div>
          </div>

          {/* Script */}
          <div>
            <label className="text-xs font-medium text-text-secondary block mb-1">
              Script <span className="text-text-disabled">({script.split(/\s+/).filter(Boolean).length} words)</span>
            </label>
            <textarea
              className="input h-36 resize-none font-mono text-xs leading-relaxed"
              placeholder="Paste your long narration here. Aim for 3-30 minutes of content. It will be split at sentence boundaries into chunks of ~60 seconds each."
              value={script}
              onChange={(e) => setScript(e.target.value)}
            />
          </div>

          {/* Chunk preview */}
          {preview && preview.chunks.length > 0 && (
            <div className="rounded-lg border border-border-subtle bg-bg-raised p-3">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-text-secondary font-medium">
                  Splits into {preview.total_chunks} chunk{preview.total_chunks === 1 ? '' : 's'}
                </span>
                <span className="text-text-muted">
                  Total ~{Math.round(preview.total_est_seconds)}s
                </span>
              </div>
              <div className="space-y-1.5">
                {preview.chunks.slice(0, 6).map((c) => (
                  <div key={c.index} className="flex items-center gap-2 text-xs">
                    <span className="text-text-disabled tabular-nums">{c.index + 1}</span>
                    <span className="text-text-muted flex-1 truncate">{c.script.slice(0, 80)}…</span>
                    <span className="text-text-disabled tabular-nums">{Math.round(c.est_duration_sec)}s</span>
                    <span className="text-text-disabled">{c.num_scenes} sc</span>
                  </div>
                ))}
                {preview.chunks.length > 6 && (
                  <div className="text-xs text-text-disabled text-center pt-1">
                    +{preview.chunks.length - 6} more…
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Settings row */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-text-secondary block mb-1">Voice</label>
              <select className="input text-sm" value={voice} onChange={(e) => setVoice(e.target.value)}>
                {VOICES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-text-secondary block mb-1">Skill</label>
              <select className="input text-sm" value={skillId} onChange={(e) => setSkillId(e.target.value)}>
                <option value="">— None —</option>
                {skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-text-secondary block mb-1">
                Chunk size <span className="text-text-disabled">({chunkWords} words)</span>
              </label>
              <input
                type="range" min={60} max={400} step={20}
                value={chunkWords}
                onChange={(e) => setChunkWords(Number(e.target.value))}
                className="w-full accent-accent"
              />
            </div>
          </div>

          {/* Quality */}
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider block mb-2">
              Quality (applied to all chunks)
            </label>
            <div className="flex flex-wrap gap-2">
              {(['subtitles', 'music', 'interpolation', 'upscaling'] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => toggle(k)}
                  className={`text-xs px-3 py-1.5 rounded border capitalize transition-colors
                    ${opts[k]
                      ? 'border-accent bg-accent/10 text-text-primary'
                      : 'border-border-subtle bg-bg-raised text-text-muted hover:border-border-base'}`}
                >
                  {k}
                </button>
              ))}
            </div>
          </div>

          {error && <p className="text-xs text-error">{error}</p>}
        </div>

        <div className="flex justify-end gap-2 px-5 py-3 border-t border-border-subtle">
          <button className="btn-ghost text-sm" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary text-sm"
            disabled={submitting || !preview || preview.chunks.length === 0}
            onClick={handleSubmit}
          >
            {submitting
              ? 'Queuing…'
              : `Queue ${preview?.total_chunks ?? 0} sub-project${preview?.total_chunks === 1 ? '' : 's'}`}
          </button>
        </div>
      </div>
    </div>
  )
}
