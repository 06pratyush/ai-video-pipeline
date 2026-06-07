import { useEffect, useRef, useState } from 'react'

export interface SetupMessage {
  step: string
  status?: 'running' | 'done' | 'error' | 'skip'
  message?: string
  detail?: string
  pct?: number
}

interface StepState {
  id: string
  label: string
  status: 'waiting' | 'running' | 'done' | 'error' | 'skip'
  message: string
  detail: string
}

const STEP_LABELS: Record<string, string> = {
  python_check: 'Python version check',
  gpu_detect:   'GPU detection',
  venv:         'Python environment',
  pytorch:      'PyTorch installation',
  deps:         'Backend dependencies',
  ffmpeg:       'FFmpeg',
  ollama:       'Ollama LLM server',
  llm:          'Language model download',
  comfyui:      'ComfyUI video engine',
  wan_model:    'Wan2.1 video model',
  frontend:     'Frontend dependencies',
}

const STEP_ORDER = Object.keys(STEP_LABELS)

export default function SetupScreen({ onComplete }: { onComplete: () => void }) {
  const [steps, setSteps] = useState<StepState[]>(
    STEP_ORDER.map((id) => ({
      id,
      label: STEP_LABELS[id],
      status: 'waiting',
      message: '',
      detail: '',
    }))
  )
  const [progress, setProgress]     = useState(0)
  const [logs, setLogs]             = useState<string[]>([])
  const [showLogs, setShowLogs]     = useState(false)
  const [fatal, setFatal]           = useState<string | null>(null)
  const [complete, setComplete]     = useState(false)
  const [retrying, setRetrying]     = useState(false)
  const logsEndRef                  = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Subscribe to IPC events from Electron main process
  useEffect(() => {
    const api = (window as Window & typeof globalThis & { electronAPI?: ElectronSetupAPI }).electronAPI
    if (!api?.onSetupMessage) {
      // In browser dev mode — simulate a fast "already set up" flow
      simulateDev(setSteps, setProgress, setComplete, onComplete)
      return
    }

    const unsub = api.onSetupMessage((msg: SetupMessage) => {
      if (msg.step === 'log') {
        setLogs((l) => [...l.slice(-499), msg.message ?? ''])
        return
      }
      if (msg.step === 'progress') {
        setProgress(msg.pct ?? 0)
        return
      }
      if (msg.step === 'fatal') {
        setFatal(msg.message ?? 'Setup failed')
        return
      }
      if (msg.step === 'complete') {
        setProgress(100)
        setComplete(true)
        setTimeout(onComplete, 1500)
        return
      }
      if (msg.step === 'start' || msg.step === 'gpu_detect') {
        if (msg.step === 'gpu_detect') {
          setLogs((l) => [...l, msg.message ?? ''])
        }
        return
      }

      // Normal step update
      setSteps((prev) =>
        prev.map((s) =>
          s.id === msg.step
            ? { ...s, status: msg.status ?? 'running', message: msg.message ?? '', detail: msg.detail ?? '' }
            : s
        )
      )
    })

    api.startSetup()
    return () => unsub?.()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRetry = () => {
    setRetrying(true)
    setFatal(null)
    setSteps((prev) => prev.map((s) => ({ ...s, status: s.status === 'error' ? 'waiting' : s.status })))
    const api = (window as Window & typeof globalThis & { electronAPI?: ElectronSetupAPI }).electronAPI
    api?.startSetup()
    setRetrying(false)
  }

  const activeStep = steps.find((s) => s.status === 'running')
  const doneCount  = steps.filter((s) => s.status === 'done' || s.status === 'skip').length

  return (
    <div className="flex flex-col h-full bg-bg-base animate-fade-in">
      {/* Header */}
      <div className="drag-region flex items-center justify-between px-6 py-4 border-b border-border-subtle">
        <div className="flex items-center gap-3 no-drag">
          <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center text-lg">🎬</div>
          <div>
            <div className="text-sm font-semibold text-text-primary">AI Video Studio</div>
            <div className="text-xs text-text-muted">First-run setup</div>
          </div>
        </div>
        <div className="no-drag text-xs text-text-muted">
          {complete ? 'Complete!' : `${doneCount} / ${steps.length} steps`}
        </div>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Steps panel */}
        <div className="w-72 border-r border-border-subtle flex flex-col overflow-y-auto py-4 px-3 gap-1">
          {steps.map((step) => (
            <StepRow key={step.id} step={step} />
          ))}
        </div>

        {/* Detail panel */}
        <div className="flex-1 flex flex-col p-6 min-w-0">

          {/* Progress bar */}
          <div className="mb-6">
            <div className="flex justify-between text-xs text-text-muted mb-1.5">
              <span>{complete ? 'Setup complete!' : activeStep ? activeStep.label : 'Preparing...'}</span>
              <span>{progress}%</span>
            </div>
            <div className="w-full bg-bg-muted rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-700 ${complete ? 'bg-success' : 'bg-accent'}`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          {/* Active step detail */}
          {activeStep && (
            <div className="card mb-4 animate-fade-in">
              <div className="text-sm font-medium text-text-primary mb-1">{activeStep.label}</div>
              <div className="text-xs text-text-secondary">{activeStep.message}</div>
              {activeStep.detail && (
                <div className="text-xs text-text-muted mt-1 font-mono">{activeStep.detail}</div>
              )}
            </div>
          )}

          {/* Fatal error */}
          {fatal && (
            <div className="card border-error/30 mb-4 animate-slide-up">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-error">✗</span>
                <span className="text-sm font-medium text-error">Setup failed</span>
              </div>
              <p className="text-xs text-text-muted mb-4">{fatal}</p>
              <button
                className="btn-primary text-sm"
                onClick={handleRetry}
                disabled={retrying}
              >
                {retrying ? 'Retrying...' : '↺ Retry Setup'}
              </button>
            </div>
          )}

          {/* Complete message */}
          {complete && (
            <div className="card border-success/30 mb-4 animate-slide-up">
              <div className="flex items-center gap-2">
                <span className="text-success text-lg">✓</span>
                <span className="text-sm font-medium text-text-primary">
                  Setup complete — launching AI Video Studio…
                </span>
              </div>
            </div>
          )}

          {/* Log toggle */}
          <div className="mt-auto">
            <button
              className="text-xs text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
              onClick={() => setShowLogs((v) => !v)}
            >
              <span>{showLogs ? '▼' : '▶'}</span>
              <span>Installation log {showLogs ? '(hide)' : '(show)'}</span>
            </button>

            {showLogs && (
              <div className="mt-2 bg-bg-raised border border-border-subtle rounded-lg p-3 h-40 overflow-y-auto font-mono text-xs text-text-muted">
                {logs.map((line, i) => (
                  <div key={i} className="leading-5">{line}</div>
                ))}
                {logs.length === 0 && <div className="text-text-disabled">No log output yet…</div>}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StepRow({ step }: { step: StepState }) {
  const icons: Record<string, string> = {
    waiting: '○',
    running: '◌',
    done:    '✓',
    error:   '✗',
    skip:    '–',
  }
  const colors: Record<string, string> = {
    waiting: 'text-text-disabled',
    running: 'text-accent animate-pulse',
    done:    'text-success',
    error:   'text-error',
    skip:    'text-text-disabled',
  }

  return (
    <div className={`flex items-start gap-2.5 px-2 py-1.5 rounded-md
      ${step.status === 'running' ? 'bg-accent/5' : ''}`}>
      <span className={`text-xs mt-0.5 w-3 shrink-0 ${colors[step.status]}`}>
        {icons[step.status]}
      </span>
      <div className="min-w-0">
        <div className={`text-xs ${step.status === 'waiting' ? 'text-text-disabled' : 'text-text-secondary'}`}>
          {step.label}
        </div>
        {step.message && step.status !== 'waiting' && (
          <div className="text-xs text-text-muted truncate mt-0.5">{step.message}</div>
        )}
      </div>
    </div>
  )
}

// Dev-mode simulator (no Electron IPC available)
function simulateDev(
  setSteps: React.Dispatch<React.SetStateAction<StepState[]>>,
  setProgress: React.Dispatch<React.SetStateAction<number>>,
  setComplete: React.Dispatch<React.SetStateAction<boolean>>,
  onComplete: () => void,
) {
  const marks: Array<[string, 'done' | 'skip', string]> = [
    ['python_check', 'done',  'Python 3.11.9 ✓'],
    ['gpu_detect',   'skip',  'GPU: RTX 4060 (8 GB)'],
    ['venv',         'skip',  'Virtual environment already exists'],
    ['pytorch',      'skip',  'PyTorch 2.3.0+cu121 already installed'],
    ['deps',         'skip',  'Backend dependencies already installed'],
    ['ffmpeg',       'skip',  'FFmpeg found on PATH'],
    ['ollama',       'skip',  'Ollama found: /usr/bin/ollama'],
    ['llm',          'skip',  'gemma3:4b already installed'],
    ['comfyui',      'skip',  'ComfyUI found at app/runtime/comfyui'],
    ['wan_model',    'skip',  'Wan model already present'],
    ['frontend',     'skip',  'Frontend dependencies already installed'],
  ]
  let i = 0
  const tick = () => {
    if (i >= marks.length) {
      setProgress(100)
      setComplete(true)
      setTimeout(onComplete, 1000)
      return
    }
    const [id, status, message] = marks[i++]
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, status, message } : s)))
    setProgress(Math.round((i / marks.length) * 100))
    setTimeout(tick, 80)
  }
  setTimeout(tick, 400)
}

// Type for the Electron IPC bridge
interface ElectronSetupAPI {
  onSetupMessage: (cb: (msg: SetupMessage) => void) => (() => void) | undefined
  startSetup: () => void
}
