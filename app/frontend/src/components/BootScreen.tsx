import { useEffect, useState } from 'react'
import { useModelStore } from '@/stores/modelStore'

type Step = { label: string; status: 'waiting' | 'running' | 'done' | 'error' }

export default function BootScreen({ onReady }: { onReady: () => void }) {
  const { checkDaemon, fetchAll } = useModelStore()
  const [steps, setSteps] = useState<Step[]>([
    { label: 'Connecting to backend daemon', status: 'running' },
    { label: 'Loading model registry',        status: 'waiting' },
    { label: 'Fetching skills',               status: 'waiting' },
    { label: 'Reading system status',         status: 'waiting' },
  ])
  const [error, setError] = useState<string | null>(null)

  const mark = (i: number, status: Step['status']) =>
    setSteps((s) => s.map((step, idx) => (idx === i ? { ...step, status } : step)))

  useEffect(() => {
    let attempts = 0
    const maxAttempts = 15

    const tryConnect = async () => {
      attempts++
      const ok = await checkDaemon()
      if (!ok) {
        if (attempts >= maxAttempts) {
          mark(0, 'error')
          setError('Cannot reach the backend daemon at localhost:7860.\nMake sure start.bat has been run.')
          return
        }
        setTimeout(tryConnect, 2000)
        return
      }
      mark(0, 'done')
      mark(1, 'running')
      try {
        // race fetchAll against a 10s timeout so a slow backend doesn't block forever
        await Promise.race([
          fetchAll(),
          new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 10_000)),
        ])
      } catch {
        // non-fatal — proceed anyway with whatever loaded
      }
      mark(1, 'done')
      mark(2, 'done')
      mark(3, 'done')
      setTimeout(onReady, 300)
    }

    tryConnect()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col items-center justify-center h-full bg-bg-base gap-8 animate-fade-in">
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center mb-2">
          <span className="text-2xl">🎬</span>
        </div>
        <h1 className="text-xl font-semibold text-text-primary">AI Video Studio</h1>
        <p className="text-sm text-text-muted">Starting up…</p>
      </div>

      <div className="flex flex-col gap-2 w-72">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-3">
            <StepIcon status={step.status} />
            <span className={`text-sm ${step.status === 'waiting' ? 'text-text-disabled' : step.status === 'error' ? 'text-error' : 'text-text-secondary'}`}>
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {error && (
        <div className="w-80 bg-error/10 border border-error/30 rounded-card p-4 text-sm text-error whitespace-pre-wrap">
          {error}
        </div>
      )}
    </div>
  )
}

function StepIcon({ status }: { status: Step['status'] }) {
  if (status === 'done')    return <span className="text-success text-sm">✓</span>
  if (status === 'error')   return <span className="text-error text-sm">✗</span>
  if (status === 'running') return <Spinner />
  return <span className="w-4 h-4 rounded-full border border-border-subtle" />
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin text-accent" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}
