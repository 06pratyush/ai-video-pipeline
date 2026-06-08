import { useEffect, useState } from 'react'
import { api, ProjectVersion } from '@/api/backend'
import { useActiveProject, useProjectStore } from '@/stores/projectStore'

export default function VersionHistory({ onClose }: { onClose: () => void }) {
  const project = useActiveProject()
  const { fetchProjects, fetchScenes } = useProjectStore()
  const [versions, setVersions] = useState<ProjectVersion[]>([])
  const [loading, setLoading]   = useState(true)
  const [busy, setBusy]         = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = async () => {
    if (!project) return
    setLoading(true)
    try {
      const list = await api.versions.list(project.id)
      setVersions(list)
    } catch {}
    setLoading(false)
  }
  useEffect(() => { load() }, [project?.id])

  if (!project) return null

  const handleSnapshot = async () => {
    setBusy('new')
    try {
      await api.versions.create(project.id, prompt('Optional label?') || undefined)
      await load()
    } catch {}
    setBusy(null)
  }

  const handleRestore = async (v: ProjectVersion) => {
    if (!confirm(`Restore project to v${v.version_num}? Current scenes will be overwritten with snapshot prompts.`)) return
    setBusy(v.id)
    try {
      await api.versions.restore(project.id, v.id)
      await fetchProjects()
      await fetchScenes(project.id)
    } catch {}
    setBusy(null)
  }

  const handleDelete = async (v: ProjectVersion) => {
    if (!confirm(`Delete version v${v.version_num}? The archived video file will also be deleted.`)) return
    await api.versions.delete(project.id, v.id)
    await load()
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6">
      <div className="bg-bg-surface border border-border-base rounded-card w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">

        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Version History — {project.name}</h2>
            <p className="text-xs text-text-muted mt-0.5">Snapshots are auto-saved after every successful render</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="btn-primary text-xs px-3 py-1.5"
              disabled={busy === 'new'}
              onClick={handleSnapshot}
            >
              {busy === 'new' ? 'Saving…' : '+ Snapshot now'}
            </button>
            <button className="text-text-muted hover:text-text-primary text-lg" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && <p className="text-sm text-text-muted text-center mt-8">Loading…</p>}
          {!loading && versions.length === 0 && (
            <p className="text-sm text-text-disabled text-center mt-10">
              No versions yet. Run a generation or click "Snapshot now" to create one.
            </p>
          )}
          <div className="space-y-2">
            {versions.map((v) => {
              const isOpen = expanded === v.id
              const scenes = v.snapshot.scenes ?? []
              return (
                <div key={v.id} className="rounded-lg bg-bg-raised border border-border-subtle">
                  <div className="flex items-start gap-3 px-3 py-2.5">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text-primary">
                          v{v.version_num}
                        </span>
                        {v.label && (
                          <span className="text-xs text-text-muted truncate">— {v.label}</span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-text-disabled mt-0.5">
                        <span>{new Date(v.created_at).toLocaleString()}</span>
                        {v.duration && <span>{v.duration}s</span>}
                        <span>{scenes.length} scenes</span>
                        {v.snapshot.skill_id && <span>skill: {v.snapshot.skill_id}</span>}
                        {v.final_path && <span className="text-success">archived</span>}
                      </div>
                    </div>
                    <div className="flex flex-col gap-1 shrink-0 items-end">
                      <div className="flex gap-1">
                        <button
                          className="text-xs px-2 py-1 text-text-muted hover:text-text-primary border border-border-subtle hover:border-border-base rounded transition-colors"
                          onClick={() => setExpanded(isOpen ? null : v.id)}
                        >
                          {isOpen ? 'Hide' : 'Details'}
                        </button>
                        <button
                          className="text-xs px-2 py-1 text-accent hover:text-accent/80 border border-accent/30 hover:border-accent rounded transition-colors disabled:opacity-50"
                          disabled={busy === v.id}
                          onClick={() => handleRestore(v)}
                        >
                          Restore
                        </button>
                        <button
                          className="text-xs px-2 py-1 text-text-disabled hover:text-error transition-colors"
                          onClick={() => handleDelete(v)}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </div>
                  {isOpen && (
                    <div className="px-3 pb-3 pt-1 border-t border-border-subtle text-xs text-text-muted space-y-2">
                      {v.snapshot.script && (
                        <div>
                          <span className="text-text-disabled uppercase tracking-wider">Script</span>
                          <p className="font-mono text-text-secondary mt-0.5 leading-relaxed line-clamp-4">
                            {v.snapshot.script}
                          </p>
                        </div>
                      )}
                      {scenes.length > 0 && (
                        <div>
                          <span className="text-text-disabled uppercase tracking-wider">Scenes</span>
                          <ol className="mt-0.5 space-y-1 list-decimal list-inside">
                            {scenes.map((s) => (
                              <li key={s.index} className="text-text-secondary leading-snug line-clamp-2">
                                {s.prompt}
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
