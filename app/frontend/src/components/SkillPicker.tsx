import { useModelStore } from '@/stores/modelStore'
import { Skill } from '@/api/backend'

const PACING_COLOR: Record<string, string> = {
  slow: 'text-info', medium: 'text-warning', fast: 'text-success',
}
const PACING_LABEL: Record<string, string> = {
  slow: 'Slow', medium: 'Medium', fast: 'Fast',
}

const VOICE_SHORT: Record<string, string> = {
  af_sarah: 'Sarah', af_bella: 'Bella', af_heart: 'Heart', af_nicole: 'Nicole',
  am_adam: 'Adam', am_michael: 'Michael', bf_emma: 'Emma', bm_george: 'George',
}

export default function SkillPicker({
  value, onChange,
}: { value: string | null; onChange: (id: string | null) => void }) {
  const { skills } = useModelStore()

  return (
    <div className="grid grid-cols-2 gap-2">
      {skills.map((skill) => (
        <SkillCard
          key={skill.id}
          skill={skill}
          selected={value === skill.id}
          onSelect={() => onChange(value === skill.id ? null : skill.id)}
        />
      ))}
    </div>
  )
}

function SkillCard({ skill, selected, onSelect }: {
  skill: Skill; selected: boolean; onSelect: () => void
}) {
  const voiceName = VOICE_SHORT[skill.voice] ?? skill.voice
  const fxCount = skill.post_processing.length

  return (
    <button
      onClick={onSelect}
      className={`text-left p-3 rounded-lg border transition-all duration-150
        ${selected
          ? 'border-accent bg-accent/10 ring-1 ring-accent/40'
          : 'border-border-subtle bg-bg-raised hover:border-border-base hover:bg-bg-overlay'
        }`}
    >
      <div className="text-sm font-medium text-text-primary mb-0.5">{skill.name}</div>
      <div className="text-xs text-text-muted mb-2 leading-snug">{skill.description}</div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs ${PACING_COLOR[skill.scene_pacing] ?? 'text-text-muted'}`}>
          {PACING_LABEL[skill.scene_pacing] ?? skill.scene_pacing}
        </span>
        <span className="text-xs text-text-disabled">{skill.aspect_ratio}</span>
        <span className="text-xs text-text-disabled">{voiceName}</span>
        {fxCount > 0 && (
          <span className="text-xs text-text-disabled">{fxCount} fx</span>
        )}
        {skill.subtitles && (
          <span className="text-xs text-accent/60">CC</span>
        )}
      </div>
    </button>
  )
}
