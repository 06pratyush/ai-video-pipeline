import { useActiveProject, useProjectStore } from '@/stores/projectStore'
import { Scene } from '@/api/backend'

const STATUS_COLOR: Record<string, string> = {
  pending:    'border-border-subtle',
  generating: 'border-info animate-pulse-slow',
  done:       'border-success/40',
  error:      'border-error/40',
  locked:     'border-warning/40',
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  pending:    { label: 'Pending',    cls: 'badge-muted' },
  generating: { label: 'Generating', cls: 'badge-info' },
  done:       { label: 'Done',       cls: 'badge-success' },
  error:      { label: 'Error',      cls: 'badge-error' },
  locked:     { label: 'Locked',     cls: 'badge-warning' },
}

export default function ScenesGrid() {
  const project = useActiveProject()
  const { scenes, updateScene } = useProjectStore()

  if (!project) {
    return <div className="flex items-center justify-center h-full text-text-disabled text-sm">
      No project selected.
    </div>
  }

  const projectScenes = scenes[project.id] ?? []

  if (projectScenes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-text-disabled">
        <span className="text-3xl">🎞</span>
        <p className="text-sm">Scenes appear here after generation starts.</p>
      </div>
    )
  }

  return (
    <div className="p-5 overflow-y-auto h-full">
      <div className="grid grid-cols-2 gap-3">
        {projectScenes.map((scene) => (
          <SceneCard
            key={scene.id}
            scene={scene}
            onLockToggle={() =>
              updateScene(project.id, scene.id, {
                status: scene.status === 'locked' ? 'pending' : 'locked',
              })
            }
          />
        ))}
      </div>
    </div>
  )
}

function SceneCard({ scene, onLockToggle }: { scene: Scene; onLockToggle: () => void }) {
  const badge = STATUS_BADGE[scene.status] ?? { label: scene.status, cls: 'badge-muted' }

  return (
    <div className={`bg-bg-raised border rounded-card p-3 flex flex-col gap-2 ${STATUS_COLOR[scene.status] ?? 'border-border-subtle'}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">Scene {scene.index + 1}</span>
        <span className={badge.cls}>{badge.label}</span>
      </div>

      {/* Thumbnail placeholder / actual image */}
      <div className="w-full h-24 bg-bg-muted rounded-md flex items-center justify-center overflow-hidden">
        {scene.thumbnail_path ? (
          <img src={scene.thumbnail_path} className="w-full h-full object-cover" alt="" />
        ) : (
          <span className="text-text-disabled text-xs">No preview</span>
        )}
      </div>

      {scene.prompt && (
        <p className="text-xs text-text-muted leading-relaxed line-clamp-3">{scene.prompt}</p>
      )}

      {scene.error_message && (
        <p className="text-xs text-error line-clamp-2">{scene.error_message}</p>
      )}

      <div className="flex gap-1 mt-auto">
        <button
          className="btn-ghost text-xs py-1 flex-1"
          onClick={onLockToggle}
          title={scene.status === 'locked' ? 'Unlock scene' : 'Lock scene (skip on re-generate)'}
        >
          {scene.status === 'locked' ? '🔓 Unlock' : '🔒 Lock'}
        </button>
        {scene.video_path && (
          <button
            className="btn-ghost text-xs py-1"
            onClick={() => (window as Window & typeof globalThis & { electronAPI?: { openPath: (p: string) => void } }).electronAPI?.openPath(scene.video_path!)}
          >
            ▶ Play
          </button>
        )}
      </div>
    </div>
  )
}
