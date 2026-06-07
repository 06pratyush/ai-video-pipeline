import { useState } from 'react'
import { useProjectStore } from '@/stores/projectStore'

export default function NewProjectModal({ onClose }: { onClose: () => void }) {
  const { createProject, setActiveProject } = useProjectStore()
  const [name,   setName]   = useState('')
  const [topic,  setTopic]  = useState('')
  const [saving, setSaving] = useState(false)
  const [error,  setError]  = useState('')

  const submit = async () => {
    const n = name.trim()
    const t = topic.trim()
    if (!n || !t) {
      setError('Name and topic are required.')
      return
    }
    const name_ = n
    const topic_ = t
    setSaving(true)
    try {
      const project = await createProject({ name: name_, topic: topic_, script: '' })
      setActiveProject(project.id)
      onClose()
    } catch (e) {
      setError(String(e))
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-bg-surface border border-border-base rounded-card p-6 w-96 shadow-2xl animate-slide-up">
        <h2 className="text-base font-semibold text-text-primary mb-4">New Project</h2>

        <div className="flex flex-col gap-3 mb-5">
          <div>
            <label className="text-xs text-text-secondary block mb-1">Project name</label>
            <input
              className="input text-sm"
              placeholder="My first video"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-text-secondary block mb-1">Topic / file label</label>
            <input
              className="input text-sm"
              placeholder="quantum-computing"
              value={topic}
              onChange={(e) => setTopic(e.target.value.replace(/\s+/g, '-').toLowerCase())}
            />
          </div>
        </div>

        {error && <p className="text-xs text-error mb-3">{error}</p>}

        <div className="flex gap-2 justify-end">
          <button className="btn-ghost text-sm" onClick={onClose}>Cancel</button>
          <button className="btn-primary text-sm" onClick={submit} disabled={saving}>
            {saving ? 'Creating…' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  )
}
