import { useState } from 'react'
import { useProjectStore } from '@/stores/projectStore'
import { Project } from '@/api/backend'

export default function ProjectLibrary({ onNewProject }: { onNewProject: () => void }) {
  const { projects, activeProjectId, setActiveProject, deleteProject } = useProjectStore()
  const [search, setSearch] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const filtered = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.topic.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <aside className="w-56 shrink-0 flex flex-col border-r border-border-subtle bg-bg-surface h-full">
      {/* Search */}
      <div className="p-3 border-b border-border-subtle">
        <input
          className="input text-xs py-1.5"
          placeholder="Search projects…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Project list */}
      <div className="flex-1 overflow-y-auto py-1">
        {filtered.length === 0 && (
          <p className="text-xs text-text-disabled text-center mt-8 px-4">
            {search ? 'No matches' : 'No projects yet'}
          </p>
        )}
        {filtered.map((p) => (
          <ProjectRow
            key={p.id}
            project={p}
            active={p.id === activeProjectId}
            onSelect={() => setActiveProject(p.id)}
            onDelete={() => setConfirmDelete(p.id)}
          />
        ))}
      </div>

      {/* New project */}
      <div className="p-3 border-t border-border-subtle">
        <button className="btn-primary w-full text-xs py-2" onClick={onNewProject}>
          + New Project
        </button>
      </div>

      {/* Delete confirm dialog */}
      {confirmDelete && (
        <DeleteDialog
          project={projects.find((p) => p.id === confirmDelete)!}
          onConfirm={async () => {
            await deleteProject(confirmDelete)
            setConfirmDelete(null)
          }}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </aside>
  )
}

function ProjectRow({
  project, active, onSelect, onDelete,
}: { project: Project; active: boolean; onSelect: () => void; onDelete: () => void }) {
  const statusColor: Record<string, string> = {
    idle:    'bg-text-disabled',
    queued:  'bg-warning',
    running: 'bg-info animate-pulse',
    done:    'bg-success',
    error:   'bg-error',
  }

  return (
    <div
      className={`group flex items-start gap-2 px-3 py-2.5 cursor-pointer transition-colors
        ${active ? 'bg-accent/10 border-r-2 border-accent' : 'hover:bg-bg-overlay'}`}
      onClick={onSelect}
    >
      <span className={`status-dot mt-1.5 shrink-0 ${statusColor[project.status] ?? 'bg-text-disabled'}`} />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-text-primary truncate">{project.name}</div>
        <div className="text-xs text-text-muted truncate">{project.topic}</div>
        <div className="text-xs text-text-disabled mt-0.5">
          {new Date(project.created_at).toLocaleDateString()}
        </div>
      </div>
      <button
        className="opacity-0 group-hover:opacity-100 text-text-disabled hover:text-error transition-all p-0.5"
        onClick={(e) => { e.stopPropagation(); onDelete() }}
      >
        ✕
      </button>
    </div>
  )
}

function DeleteDialog({ project, onConfirm, onCancel }: {
  project: Project; onConfirm: () => void; onCancel: () => void
}) {
  return (
    <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-bg-surface border border-border-base rounded-card p-5 w-72 shadow-2xl">
        <p className="text-sm text-text-primary mb-1">Delete "{project.name}"?</p>
        <p className="text-xs text-text-muted mb-5">This cannot be undone.</p>
        <div className="flex gap-2 justify-end">
          <button className="btn-ghost text-xs" onClick={onCancel}>Cancel</button>
          <button className="btn-danger text-xs" onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  )
}
