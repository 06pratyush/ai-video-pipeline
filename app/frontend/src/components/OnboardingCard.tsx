import { useModelStore } from '@/stores/modelStore'

const STEPS = [
  { num: '①', title: 'Write or paste your script',    sub: 'Any narration text — 2 to 5 sentences works best' },
  { num: '②', title: 'Pick a Skill',                  sub: 'Documentary, Explainer, Product, Cinematic, Short' },
  { num: '③', title: 'Choose a voice',                sub: '8 voices across American and British accents' },
  { num: '④', title: 'Hit Generate',                  sub: 'Sit back — we handle scenes, voice, and final cut' },
  { num: '⑤', title: 'Download and share',            sub: 'MP4 ready for Instagram, YouTube, TikTok, or anywhere' },
]

export default function OnboardingCard({ onDismiss }: { onDismiss: (dontShow: boolean) => void }) {
  const { systemStatus } = useModelStore()
  const hw = systemStatus?.hardware
  const svc = systemStatus?.services

  return (
    <div className="flex items-center justify-center h-full bg-bg-base/80 backdrop-blur-sm animate-fade-in">
      <div className="w-[560px] bg-bg-surface border border-border-subtle rounded-card shadow-2xl p-8 animate-slide-up">

        {/* Header */}
        <div className="mb-7">
          <h2 className="text-lg font-semibold text-text-primary mb-1">Welcome to AI Video Studio</h2>
          <p className="text-sm text-text-secondary">
            Generate cinematic videos from text — fully on your machine.
          </p>
        </div>

        {/* Steps */}
        <div className="flex flex-col gap-4 mb-7">
          {STEPS.map((step) => (
            <div key={step.num} className="flex gap-4">
              <span className="text-lg text-accent w-6 shrink-0 mt-0.5">{step.num}</span>
              <div>
                <div className="text-sm font-medium text-text-primary">{step.title}</div>
                <div className="text-xs text-text-muted mt-0.5">{step.sub}</div>
              </div>
            </div>
          ))}
        </div>

        {/* System Status */}
        <div className="bg-bg-raised border border-border-subtle rounded-lg p-4 mb-6 text-xs flex flex-col gap-2">
          <div className="text-text-muted font-medium mb-1">System Status</div>
          <StatusRow
            label="Ollama / LLM"
            ok={svc?.ollama.running ?? false}
            detail={svc?.ollama.models?.length
              ? (svc.ollama.models as Array<{name:string}>)[0]?.name ?? 'ready'
              : 'not detected'}
          />
          <StatusRow
            label="ComfyUI / Video"
            ok={svc?.comfyui.running ?? false}
            detail={svc?.comfyui.running ? 'ready' : 'not running — will start on first generation'}
          />
          <StatusRow label="Kokoro TTS" ok detail="ready" />
          {hw && (
            <StatusRow
              label={`GPU: ${hw.gpu_name}`}
              ok={hw.vram_total_gb > 0}
              detail={hw.vram_total_gb > 0 ? `${hw.vram_total_gb} GB VRAM` : 'no GPU detected'}
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <button
            className="text-xs text-text-muted hover:text-text-secondary transition-colors"
            onClick={() => onDismiss(true)}
          >
            Don't show again
          </button>
          <button className="btn-primary px-5 py-2 text-sm" onClick={() => onDismiss(false)}>
            Let's start ▸
          </button>
        </div>
      </div>
    </div>
  )
}

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={ok ? 'text-success' : 'text-text-disabled'}>
        {ok ? '✓' : '○'}
      </span>
      <span className="text-text-secondary w-32 shrink-0">{label}</span>
      <span className="text-text-muted">{detail}</span>
    </div>
  )
}
