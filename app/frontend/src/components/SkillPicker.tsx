import { useModelStore } from '@/stores/modelStore'
import { Skill } from '@/api/backend'

const PACING_LABEL: Record<string, string> = { slow: 'Slow', medium: 'Medium', fast: 'Fast' }
const PACING_COLOR: Record<string, string> = {
  slow: 'text-info', medium: 'text-warning', fast: 'text-success',
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
      <div className="text-xs text-text-muted mb-1.5">{skill.description}</div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs ${PACING_COLOR[skill.scene_pacing] ?? 'text-text-muted'}`}>
          {PACING_LABEL[skill.scene_pacing] ?? skill.scene_pacing}
        </span>
        <span className="text-xs text-text-disabled">{skill.aspect_ratio}</span>
        {skill.subtitles && <span className="text-xs text-text-disabled">subtitles</span>}
      </div>
    </button>
  )
}
