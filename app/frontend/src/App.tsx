import { useState, useEffect } from 'react'
import BootScreen     from './components/BootScreen'
import OnboardingCard from './components/OnboardingCard'
import ProjectLibrary from './components/ProjectLibrary'
import ScriptEditor   from './components/ScriptEditor'
import ScenesGrid     from './components/ScenesGrid'
import RenderPanel    from './components/RenderPanel'
import GenerationQueue from './components/GenerationQueue'
import NewProjectModal from './components/NewProjectModal'
import { useProjectStore } from './stores/projectStore'
import { useModelStore }   from './stores/modelStore'
import { SystemStatus }    from './api/backend'

type AppState = 'booting' | 'onboarding' | 'main'
type Tab = 'script' | 'scenes' | 'render'

const ONBOARDING_KEY = 'avs_skip_onboarding'

export default function App() {
  const [appState,      setAppState]      = useState<AppState>('booting')
  const [tab,           setTab]           = useState<Tab>('script')
  const [showNewModal,  setShowNewModal]  = useState(false)
  const [sysExpanded,   setSysExpanded]   = useState(false)

  const { fetchProjects } = useProjectStore()
  const { systemStatus }  = useModelStore()

  const handleBootReady = () => {
    fetchProjects()
    const skip = localStorage.getItem(ONBOARDING_KEY) === 'true'
    setAppState(skip ? 'main' : 'onboarding')
  }

  const handleOnboardingDismiss = (dontShow: boolean) => {
    if (dontShow) localStorage.setItem(ONBOARDING_KEY, 'true')
    setAppState('main')
  }

  if (appState === 'booting') {
    return <BootScreen onReady={handleBootReady} />
  }

  if (appState === 'onboarding') {
    return <OnboardingCard onDismiss={handleOnboardingDismiss} />
  }

  return (
    <div className="flex flex-col h-full bg-bg-base text-text-primary">
      {/* Title bar / top bar */}
      <TitleBar
        sysExpanded={sysExpanded}
        onToggleSys={() => setSysExpanded(!sysExpanded)}
        systemStatus={systemStatus}
      />

      {/* System status dropdown */}
      {sysExpanded && systemStatus && (
        <SystemBar status={systemStatus} onClose={() => setSysExpanded(false)} />
      )}

      {/* Main layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left sidebar */}
        <ProjectLibrary onNewProject={() => setShowNewModal(true)} />

        {/* Center editor */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Tab bar */}
          <div className="flex items-center gap-1 px-4 pt-3 pb-0 border-b border-border-subtle shrink-0">
            {(['script', 'scenes', 'render'] as Tab[]).map((t) => (
              <TabButton key={t} label={t} active={tab === t} onClick={() => setTab(t)} />
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0">
            {tab === 'script' && <ScriptEditor />}
            {tab === 'scenes' && <ScenesGrid />}
            {tab === 'render' && <RenderPanel />}
          </div>
        </main>
      </div>

      {/* Bottom generation queue */}
      <GenerationQueue />

      {/* Modals */}
      {showNewModal && <NewProjectModal onClose={() => setShowNewModal(false)} />}
    </div>
  )
}

function TitleBar({ sysExpanded, onToggleSys, systemStatus }: {
  sysExpanded: boolean
  onToggleSys: () => void
  systemStatus: SystemStatus | null
}) {
  const hw = systemStatus?.hardware
  const svc = systemStatus?.services
  const allOk = svc?.ollama.running

  return (
    <div className="drag-region h-10 flex items-center justify-between px-4 border-b border-border-subtle bg-bg-surface shrink-0">
      <div className="flex items-center gap-2 no-drag">
        <span className="text-sm font-semibold text-text-primary">AI Video Studio</span>
      </div>

      <button
        className="no-drag flex items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
        onClick={onToggleSys}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${allOk ? 'bg-success' : 'bg-warning'}`} />
        {hw ? `${hw.gpu_name.split(' ').slice(-2).join(' ')} · ${hw.vram_total_gb}GB` : 'System'}
        <span className="text-text-disabled">{sysExpanded ? '▲' : '▼'}</span>
      </button>
    </div>
  )
}

function SystemBar({ status, onClose }: {
  status: SystemStatus
  onClose: () => void
}) {
  const hw  = status.hardware
  const svc = status.services

  return (
    <div className="bg-bg-overlay border-b border-border-subtle px-4 py-2.5 flex items-center gap-6 text-xs animate-fade-in">
      <span className="text-text-secondary font-medium">System</span>
      <Chip ok icon="🖥" label={`${hw.gpu_name} · ${hw.vram_total_gb} GB`} />
      <Chip ok={svc.ollama.running}  icon="🤖" label={`Ollama ${svc.ollama.running ? '● running' : '○ stopped'}`} />
      <Chip ok={svc.comfyui.running} icon="🎬" label={`ComfyUI ${svc.comfyui.running ? '● running' : '○ stopped'}`} />
      <Chip ok icon="🎙" label="Kokoro TTS ready" />
      <button className="ml-auto text-text-muted hover:text-text-secondary" onClick={onClose}>✕</button>
    </div>
  )
}

function Chip({ ok, icon, label }: { ok: boolean; icon: string; label: string }) {
  return (
    <span className={`flex items-center gap-1 ${ok ? 'text-text-secondary' : 'text-text-disabled'}`}>
      <span>{icon}</span>
      <span>{label}</span>
    </span>
  )
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm capitalize transition-colors border-b-2
        ${active
          ? 'border-accent text-text-primary font-medium'
          : 'border-transparent text-text-muted hover:text-text-secondary'
        }`}
    >
      {label}
    </button>
  )
}
