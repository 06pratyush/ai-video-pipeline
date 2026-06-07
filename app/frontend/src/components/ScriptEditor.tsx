import { useState, useEffect } from 'react'
import { useProjectStore, useActiveProject } from '@/stores/projectStore'
import SkillPicker from './SkillPicker'

const VOICES = [
  { id: 'af_sarah',   label: 'Sarah — American Female' },
  { id: 'af_bella',   label: 'Bella — American Female' },
  { id: 'af_heart',   label: 'Heart — American Female' },
  { id: 'af_nicole',  label: 'Nicole — American Female' },
  { id: 'am_adam',    label: 'Adam — American Male' },
  { id: 'am_michael', label: 'Michael — American Male' },
  { id: 'bf_emma',    label: 'Emma — British Female' },
  { id: 'bm_george',  label: 'George — British Male' },
]

export default function ScriptEditor() {
  const project = useActiveProject()
  const { updateProject } = useProjectStore()

  const [script,    setScript]    = useState(project?.script    ?? '')
  const [voice,     setVoice]     = useState(project?.voice     ?? 'af_sarah')
  const [numScenes, setNumScenes] = useState(project?.num_scenes ?? 3)
  const [skillId,   setSkillId]   = useState<string | null>(project?.skill_id ?? null)
  const [saving,    setSaving]    = useState(false)
  const [dirty,     setDirty]     = useState(false)

  useEffect(() => {
    setScript(project?.script    ?? '')
    setVoice(project?.voice      ?? 'af_sarah')
    setNumScenes(project?.num_scenes ?? 3)
    setSkillId(project?.skill_id ?? null)
    setDirty(false)
  }, [project?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!project) return <EmptyState />

  const wordCount = script.trim().split(/\s+/).filter(Boolean).length
  const estDuration = Math.round(wordCount / 2.5)

  const save = async () => {
    setSaving(true)
    await updateProject(project.id, { script, voice, num_scenes: numScenes, skill_id: skillId })
    setSaving(false)
    setDirty(false)
  }

  return (
    <div className="flex flex-col gap-5 p-5 overflow-y-auto h-full">

      {/* Script textarea */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">Script</label>
          <span className="text-xs text-text-muted">
            {wordCount} words · ~{estDuration}s
          </span>
        </div>
        <textarea
          className="input h-44 resize-none font-mono text-sm leading-relaxed"
          placeholder="Write your narration here…&#10;&#10;Example: Artificial intelligence is reshaping how we create. In just a few years, tools that once required Hollywood budgets are now available to anyone with an idea."
          value={script}
          onChange={(e) => { setScript(e.target.value); setDirty(true) }}
        />
      </div>

      {/* Voice */}
      <div>
        <label className="text-xs font-medium text-text-secondary uppercase tracking-wider block mb-2">
          Voice
        </label>
        <select
          className="input text-sm"
          value={voice}
          onChange={(e) => { setVoice(e.target.value); setDirty(true) }}
        >
          {VOICES.map((v) => (
            <option key={v.id} value={v.id}>{v.label}</option>
          ))}
        </select>
      </div>

      {/* Scene count */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            Scenes
          </label>
          <span className="text-xs text-text-muted">{numScenes}</span>
        </div>
        <input
          type="range" min={1} max={8} step={1}
          value={numScenes}
          onChange={(e) => { setNumScenes(Number(e.target.value)); setDirty(true) }}
          className="w-full accent-accent"
        />
        <div className="flex justify-between text-xs text-text-disabled mt-1">
          <span>1</span><span>4</span><span>8</span>
        </div>
      </div>

      {/* Skill picker */}
      <div>
        <label className="text-xs font-medium text-text-secondary uppercase tracking-wider block mb-2">
          Skill
        </label>
        <SkillPicker value={skillId} onChange={(id) => { setSkillId(id); setDirty(true) }} />
      </div>

      {/* Save bar */}
      {dirty && (
        <div className="sticky bottom-0 flex justify-end pt-2">
          <button className="btn-primary text-sm" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex items-center justify-center h-full text-text-disabled text-sm">
      Select or create a project to start writing.
    </div>
  )
}
