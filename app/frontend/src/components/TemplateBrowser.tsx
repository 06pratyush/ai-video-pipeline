import { useEffect, useState } from 'react'
import { api, Template } from '@/api/backend'
import { useProjectStore } from '@/stores/projectStore'

export default function TemplateBrowser({
  onClose,
}: {
  onClose: () => void
}) {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState<string | null>(null)
  const [applyTarget, setApplyTarget] = useState<Template | null>(null)
  const { fetchProjects, setActiveProject } = useProjectStore()

  const load = async () => {
    setLoading(true)
    try {
      const items = await api.templates.list()
      setTemplates(items)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this template?')) return
    await api.templates.delete(id)
    load()
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6">
      <div className="bg-bg-surface border border-border-base rounded-card w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">

        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Templates</h2>
            <p className="text-xs text-text-muted mt-0.5">Reusable project configurations</p>
          </div>
          <button className="text-text-muted hover:text-text-primary text-lg" onClick={onClose}>✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <p className="text-sm text-text-muted text-center mt-8">Loading…</p>
          )}
          {!loading && templates.length === 0 && (
            <div className="text-center mt-10 text-sm text-text-muted">
              <p className="mb-1">No templates yet.</p>
              <p className="text-xs text-text-disabled">
                Save a project's settings as a template from the Render tab.
              </p>
            </div>
          )}
          <div className="space-y-2">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                onApply={() => setApplyTarget(t)}
                onDelete={() => handleDelete(t.id)}
              />
            ))}
          </div>
        </div>
      </div>

      {applyTarget && (
        <ApplyTemplateDialog
          template={applyTarget}
          applying={applying === applyTarget.id}
          onCancel={() => setApplyTarget(null)}
          onApply={async (projectName, topic) => {
            setApplying(applyTarget.id)
            try {
              const result = await api.templates.apply(applyTarget.id, {
                project_name: projectName,
                topic,
              })
              await fetchProjects()
              setActiveProject(result.project.id)
              setApplyTarget(null)
              onClose()
            } catch {}
            setApplying(null)
          }}
        />
      )}
    </div>
  )
}

function TemplateCard({
  template, onApply, onDelete,
}: { template: Template; onApply: () => void; onDelete: () => void }) {
  const fxList: string[] = []
  if (template.render_opts) {
    if (template.render_opts.subtitles)     fxList.push('Subtitles')
    if (template.render_opts.music)         fxList.push('Music')
    if (template.render_opts.interpolation) fxList.push('30fps')
    if (template.render_opts.upscaling)     fxList.push('Upscale')
  }
  return (
    <div className="flex items-start gap-3 px-3 py-3 rounded-lg bg-bg-raised border border-border-subtle">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-text-primary truncate">{template.name}</span>
          {template.use_count > 0 && (
            <span className="text-xs text-text-disabled">· used {template.use_count}×</span>
          )}
        </div>
        {template.description && (
          <p className="text-xs text-text-muted mb-1.5 line-clamp-2">{template.description}</p>
        )}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-disabled">
          {template.skill_id && <span>Skill {template.skill_id}</span>}
          <span>Voice {template.voice}</span>
          <span>{template.num_scenes} scenes</span>
          {fxList.map((fx) => (
            <span key={fx} className="text-accent/70">{fx}</span>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-1 shrink-0">
        <button className="btn-primary text-xs px-3 py-1" onClick={onApply}>Use</button>
        <button
          className="text-xs px-3 py-1 text-text-disabled hover:text-error transition-colors"
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
    </div>
  )
}

function ApplyTemplateDialog({
  template, applying, onCancel, onApply,
}: {
  template: Template
  applying: boolean
  onCancel: () => void
  onApply: (name: string, topic: string) => void
}) {
  const [name, setName] = useState('')
  const [topic, setTopic] = useState('')
  const submit = () => {
    if (name.trim() && topic.trim()) onApply(name.trim(), topic.trim())
  }
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
      <div className="bg-bg-surface border border-border-base rounded-card p-5 w-96 shadow-2xl">
        <h3 className="text-sm font-semibold text-text-primary mb-1">Apply "{template.name}"</h3>
        <p className="text-xs text-text-muted mb-4">A new project will be created with this template's settings.</p>
        <div className="flex flex-col gap-3 mb-4">
          <div>
            <label className="text-xs text-text-secondary block mb-1">Project name</label>
            <input className="input text-sm" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="text-xs text-text-secondary block mb-1">Topic</label>
            <input
              className="input text-sm"
              value={topic}
              onChange={(e) => setTopic(e.target.value.replace(/\s+/g, '-').toLowerCase())}
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button className="btn-ghost text-sm" onClick={onCancel}>Cancel</button>
          <button className="btn-primary text-sm" disabled={applying || !name.trim() || !topic.trim()} onClick={submit}>
            {applying ? 'Creating…' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  )
}
