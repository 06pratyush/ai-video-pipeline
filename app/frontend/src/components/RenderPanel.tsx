import { useState } from 'react'
import { useActiveProject } from '@/stores/projectStore'
import { useQueueStore } from '@/stores/queueStore'
import { useModelStore } from '@/stores/modelStore'
import { RenderOpts } from '@/api/backend'

export default function RenderPanel() {
  const project    = useActiveProject()
  const { skills } = useModelStore()
  const { startGeneration, progress } = useQueueStore()

  const activeSkill = skills.find((s) => s.id === project?.skill_id) ?? null

  // Quality settings — defaults pulled from skill, overridable
  const [opts, setOpts] = useState<RenderOpts>(() => ({
    subtitles:    activeSkill?.subtitles    ?? false,
    music:        !!(activeSkill?.music_mood),
    interpolation: false,
    upscaling:    false,
  }))

  if (!project) {
    return (
      <div className="flex items-center justify-center h-full text-text-disabled text-sm">
        No project selected.
      </div>
    )
  }

  const prog      = progress[project.id]
  const isRunning = project.status === 'running' || project.status === 'queued'
  const isDone    = project.status === 'done'
  const isError   = project.status === 'error'

  const toggle = (key: keyof RenderOpts) =>
    setOpts((o) => ({ ...o, [key]: !o[key] }))

  const handleGenerate = () => startGeneration(project.id, opts)

  return (
    <div className="flex flex-col gap-5 p-5 overflow-y-auto h-full">

      {/* Generation progress */}
      {isRunning && prog && (
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-text-primary capitalize">
              {prog.stage.replace(/_/g, ' ')}
            </span>
            <span className="text-xs text-text-muted">{Math.round(prog.progress * 100)}%</span>
          </div>
          <div className="w-full bg-bg-muted rounded-full h-1.5 mb-2">
            <div
              className="bg-accent h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${prog.progress * 100}%` }}
            />
          </div>
          <p className="text-xs text-text-muted">{prog.message}</p>
        </div>
      )}

      {/* Success */}
      {isDone && project.final_path && (
        <div className="card flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <span className="text-success">✓</span>
            <span className="text-sm font-medium text-text-primary">Generation complete</span>
          </div>
          <div className="flex gap-2">
            <a
              href={`http://localhost:7860/projects/${project.id}/download`}
              className="btn-primary text-sm flex-1 text-center"
              download
            >
              ⬇ Download MP4
            </a>
            <button
              className="btn-ghost text-sm"
              onClick={() =>
                (window as Window & typeof globalThis & { electronAPI?: { showInFolder: (p: string) => void } })
                  .electronAPI?.showInFolder(project.final_path!)
              }
            >
              Show in folder
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="card border-error/30">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-error">✗</span>
            <span className="text-sm font-medium text-error">Generation failed</span>
          </div>
          <p className="text-xs text-text-muted">{prog?.message || 'Check the backend logs for details.'}</p>
        </div>
      )}

      {/* Quality settings */}
      {!isRunning && (
        <div className="card">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-3">
            Quality Settings
          </h3>
          <div className="flex flex-col gap-3">
            <QualityToggle
              label="Subtitles"
              description="Auto-generate via Whisper and burn into video"
              badge={activeSkill?.subtitles ? 'skill' : undefined}
              value={opts.subtitles}
              onChange={() => toggle('subtitles')}
            />
            <QualityToggle
              label="Background Music"
              description={activeSkill?.music_mood
                ? `MusicGen · mood: ${activeSkill.music_mood.replace(/_/g, ' ')}`
                : 'Generate AI soundtrack matching the skill mood'
              }
              badge={activeSkill?.music_mood ? 'skill' : undefined}
              value={opts.music}
              onChange={() => toggle('music')}
            />
            <QualityToggle
              label="Frame Interpolation"
              description="Smooth to 30fps via minterpolate · adds ~30% render time"
              value={opts.interpolation}
              onChange={() => toggle('interpolation')}
            />
            <QualityToggle
              label="Upscaling"
              description="2× upscale to 1080p via super2xbr · adds ~20% render time"
              value={opts.upscaling}
              onChange={() => toggle('upscaling')}
            />
          </div>
        </div>
      )}

      {/* Project summary */}
      <div className="card">
        <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-3">
          Project Summary
        </h3>
        <div className="flex flex-col gap-2 text-sm">
          <Row label="Topic"  value={project.topic} />
          <Row label="Voice"  value={project.voice} />
          <Row label="Scenes" value={String(project.num_scenes)} />
          <Row label="Skill"  value={project.skill_id ?? 'None'} />
          {project.audio_duration && (
            <Row label="Audio" value={`${project.audio_duration.toFixed(1)}s`} />
          )}
          <Row label="Status" value={project.status} />
        </div>
      </div>

      {/* Generate button */}
      {!isRunning && (
        <div className="mt-auto">
          <button
            className={`btn-primary w-full py-3 text-sm font-semibold
              ${!project.script?.trim() ? 'opacity-50 cursor-not-allowed' : ''}`}
            disabled={!project.script?.trim() || isRunning}
            onClick={handleGenerate}
          >
            {isDone ? '↺ Re-generate' : '▶ Generate Video'}
          </button>
          {!project.script?.trim() && (
            <p className="text-xs text-text-muted text-center mt-2">
              Add a script in the Script tab first.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function QualityToggle({
  label, description, badge, value, onChange,
}: {
  label: string
  description: string
  badge?: string
  value: boolean
  onChange: () => void
}) {
  return (
    <div className="flex items-start gap-3">
      <button
        onClick={onChange}
        className={`mt-0.5 w-9 h-5 rounded-full transition-colors shrink-0
          ${value ? 'bg-accent' : 'bg-bg-muted border border-border-subtle'}`}
        role="switch"
        aria-checked={value}
      >
        <span
          className={`block w-3.5 h-3.5 rounded-full bg-white shadow transition-transform mx-0.5
            ${value ? 'translate-x-4' : 'translate-x-0'}`}
        />
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-text-primary">{label}</span>
          {badge && (
            <span className="text-xs text-accent/70 border border-accent/30 px-1 rounded">
              {badge}
            </span>
          )}
        </div>
        <p className="text-xs text-text-muted mt-0.5">{description}</p>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{label}</span>
      <span className="text-text-secondary">{value}</span>
    </div>
  )
}
