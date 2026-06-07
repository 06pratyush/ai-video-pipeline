import { useState, useEffect } from 'react'
import SetupScreen    from './components/SetupScreen'
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

type AppState = 'setup' | 'booting' | 'onboarding' | 'main'
type Tab = 'script' | 'scenes' | 'render'

const ONBOARDING_KEY = 'avs_skip_onboarding'

// Electron API type (undefined in browser)
interface ElectronAPI {
  onSetupNeeded?: (cb: (needed: boolean) => void) => void
  startSetup?: () => void
  onSetupMessage?: (cb: (msg: unknown) => void) => (() => void) | undefined
  openPath?: (path: string) => void
  showInFolder?: (path: string) => void
  platform?: string
}

function getElectronAPI(): ElectronAPI | undefined {
  return (window as Window & typeof globalThis & { electronAPI?: ElectronAPI }).electronAPI
}

export default function App() {
  const [appState,     setAppState]     = useState<AppState>(() => {
    // ?setup=1 in URL forces setup screen (dev preview)
    if (new URLSearchParams(window.location.search).get('setup') === '1') return 'setup'
    // In browser (no Electron), skip straight to booting
    const api = getElectronAPI()
    return api ? 'setup' : 'booting'
  })
  const [tab,          setTab]          = useState<Tab>('script')
  const [showNewModal, setShowNewModal] = useState(false)
  const { fetchProjects } = useProjectStore()
  const { systemStatus }  = useModelStore()

  // Listen for Electron's setup:needed signal
  useEffect(() => {
    // ?setup=1 keeps setup state even in browser
    if (new URLSearchParams(window.location.search).get('setup') === '1') return
    const api = getElectronAPI()
    if (!api?.onSetupNeeded) {
      // Browser: go straight to boot
      setAppState('booting')
      return
    }
    api.onSetupNeeded((needed) => {
      setAppState(needed ? 'setup' : 'booting')
    })
  }, [])

  const handleSetupComplete = () => setAppState('booting')

  const handleBootReady = () => {
    fetchProjects()
    const skip = localStorage.getItem(ONBOARDING_KEY) === 'true'
    setAppState(skip ? 'main' : 'onboarding')
  }

  const handleOnboardingDismiss = (dontShow: boolean) => {
    if (dontShow) localStorage.setItem(ONBOARDING_KEY, 'true')
    setAppState('main')
  }

  if (appState === 'setup')      return <SetupScreen onComplete={handleSetupComplete} />
  if (appState === 'booting')    return <BootScreen onReady={handleBootReady} />
  if (appState === 'onboarding') return <OnboardingCard onDismiss={handleOnboardingDismiss} />

  return (
    <div className="flex flex-col h-full bg-bg-base text-text-primary">
      <TitleBar systemStatus={systemStatus} />

      <div className="flex flex-1 min-h-0">
        <ProjectLibrary onNewProject={() => setShowNewModal(true)} />

        <main className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center gap-1 px-4 pt-3 pb-0 border-b border-border-subtle shrink-0">
            {(['script', 'scenes', 'render'] as Tab[]).map((t) => (
              <TabButton key={t} label={t} active={tab === t} onClick={() => setTab(t)} />
            ))}
          </div>

          <div className="flex-1 min-h-0">
            {tab === 'script' && <ScriptEditor />}
            {tab === 'scenes' && <ScenesGrid />}
            {tab === 'render' && <RenderPanel />}
          </div>
        </main>
      </div>

      <GenerationQueue />
      {showNewModal && <NewProjectModal onClose={() => setShowNewModal(false)} />}
    </div>
  )
}

function TitleBar({ systemStatus }: { systemStatus: SystemStatus | null }) {
  const hw  = systemStatus?.hardware
  const svc = systemStatus?.services

  return (
    <div className="drag-region h-10 flex items-center justify-between px-4 border-b border-border-subtle bg-bg-surface shrink-0">
      <span className="text-sm font-semibold text-text-primary no-drag">AI Video Studio</span>
      <div className="no-drag flex items-center gap-1.5 text-xs text-text-muted">
        <span className={`w-1.5 h-1.5 rounded-full ${svc?.ollama.running ? 'bg-success' : 'bg-warning'}`} />
        <span>{hw ? `${hw.gpu_name.split(' ').slice(-2).join(' ')} · ${hw.vram_total_gb}GB` : 'System'}</span>
      </div>
    </div>
  )
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm capitalize transition-colors border-b-2
        ${active
          ? 'border-accent text-text-primary font-medium'
          : 'border-transparent text-text-muted hover:text-text-secondary'}`}
    >
      {label}
    </button>
  )
}
