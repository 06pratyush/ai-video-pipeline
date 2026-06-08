import { useState, useEffect } from 'react'
import { api, BatchItem, Template, RenderOpts } from '@/api/backend'
import { useProjectStore } from '@/stores/projectStore'

interface BatchRow {
  name: string
  topic: string
  script: string
}

export default function BatchModal({ onClose }: { onClose: () => void }) {
  const { fetchProjects } = useProjectStore()
  const [templates, setTemplates]   = useState<Template[]>([])
  const [templateId, setTemplateId] = useState<string>('')
  const [rows, setRows]             = useState<BatchRow[]>([
    { name: '', topic: '', script: '' },
  ])
  const [opts, setOpts] = useState<RenderOpts>({
    subtitles: false, music: false, interpolation: false, upscaling: false,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState('')

  useEffect(() => {
    api.templates.list().then(setTemplates).catch(() => {})
  }, [])

  const updateRow = (i: number, patch: Partial<BatchRow>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  const addRow = () => setRows((rs) => [...rs, { name: '', topic: '', script: '' }])
  const delRow = (i: number) => setRows((rs) => rs.filter((_, idx) => idx !== i))

  const validRows = rows.filter((r) => r.name.trim() && r.topic.trim() && r.script.trim())

  const submit = async () => {
    if (validRows.length === 0) {
      setError('Add at least one complete row.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const items: BatchItem[] = validRows.map((r) => ({
        name: r.name.trim(),
        topic: r.topic.trim().replace(/\s+/g, '-').toLowerCase(),
        script: r.script.trim(),
      }))
      await api.batch.create(items, {
        template_id: templateId || undefined,
        render_opts: opts,
      })
      await fetchProjects()
      onClose()
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  const toggle = (key: keyof RenderOpts) =>
    setOpts((o) => ({ ...o, [key]: !o[key] }))

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6">
      <div className="bg-bg-surface border border-border-base rounded-card w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl">

        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Batch Generation</h2>
            <p className="text-xs text-text-muted mt-0.5">Queue multiple projects to render sequentially</p>
          </div>
          <button className="text-text-muted hover:text-text-primary text-lg" onClick={onClose}>✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {/* Template selector */}
          {templates.length > 0 && (
            <div>
              <label className="text-xs font-medium text-text-secondary uppercase tracking-wider block mb-1.5">
                Apply Template (optional)
              </label>
              <select
                className="input text-sm"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">— None — use defaults —</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Rows */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                Projects ({validRows.length} / {rows.length} ready)
              </label>
              <button className="text-xs text-accent hover:text-accent/80" onClick={addRow}>+ Add row</button>
            </div>
            <div className="space-y-3">
              {rows.map((row, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-start">
                  <input
                    className="input text-xs col-span-3 py-1.5"
                    placeholder="Name"
                    value={row.name}
                    onChange={(e) => updateRow(i, { name: e.target.value })}
                  />
                  <input
                    className="input text-xs col-span-3 py-1.5"
                    placeholder="topic-slug"
                    value={row.topic}
                    onChange={(e) => updateRow(i, { topic: e.target.value.replace(/\s+/g, '-').toLowerCase() })}
                  />
                  <textarea
                    className="input text-xs col-span-5 py-1.5 h-12 resize-none font-mono"
                    placeholder="Script narration…"
                    value={row.script}
                    onChange={(e) => updateRow(i, { script: e.target.value })}
                  />
                  <button
                    className="col-span-1 text-text-disabled hover:text-error transition-colors text-sm py-1.5"
                    onClick={() => delRow(i)}
                    disabled={rows.length === 1}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Render opts */}
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider block mb-2">
              Quality (applied to all projects)
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
            disabled={submitting || validRows.length === 0}
            onClick={submit}
          >
            {submitting ? 'Queuing…' : `Queue ${validRows.length} project${validRows.length === 1 ? '' : 's'}`}
          </button>
        </div>
      </div>
    </div>
  )
}
