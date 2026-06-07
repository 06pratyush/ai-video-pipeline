const BASE = 'http://localhost:7860'

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`${method} ${path} → ${res.status}: ${err}`)
  }
  return res.json()
}

// ── System ────────────────────────────────────────────────────────────────────
export const api = {
  system: {
    health: ()  => req<{ status: string }>('GET', '/system/health'),
    status: ()  => req<SystemStatus>('GET', '/system/status'),
    startOllama:  () => req('POST', '/system/services/ollama/start'),
    startComfyUI: () => req('POST', '/system/services/comfyui/start'),
  },

  // ── Projects ───────────────────────────────────────────────────────────────
  projects: {
    list:   ()                  => req<Project[]>('GET', '/projects/'),
    get:    (id: string)        => req<Project>('GET', `/projects/${id}`),
    create: (data: ProjectCreate) => req<Project>('POST', '/projects/', data),
    update: (id: string, data: Partial<ProjectCreate>) =>
      req<Project>('PATCH', `/projects/${id}`, data),
    delete: (id: string)        => req('DELETE', `/projects/${id}`),
    scenes: (id: string)        => req<Scene[]>('GET', `/projects/${id}/scenes`),
    updateScene: (projectId: string, sceneId: string, data: Partial<Scene>) =>
      req<Scene>('PATCH', `/projects/${projectId}/scenes/${sceneId}`, data),
    downloadUrl: (id: string)   => `${BASE}/projects/${id}/download`,
  },

  // ── Generation ────────────────────────────────────────────────────────────
  generation: {
    start: (projectId: string, renderOpts?: RenderOpts) =>
      req<{ queued: boolean; queue_item_id: string }>(
        'POST', '/generation/start',
        { project_id: projectId, render_opts: renderOpts ?? null },
      ),
    cancel:  (queueItemId: string) => req('POST', `/generation/cancel/${queueItemId}`),
    queue:   ()  => req<QueueItem[]>('GET', '/generation/queue'),
    history: ()  => req<QueueItem[]>('GET', '/generation/history'),
  },

  // ── Models ────────────────────────────────────────────────────────────────
  models: {
    all:     () => req<ModelInfo[]>('GET', '/models/'),
    llm:     () => req<ModelInfo[]>('GET', '/models/llm'),
    video:   () => req<ModelInfo[]>('GET', '/models/video'),
    tts:     () => req<ModelInfo[]>('GET', '/models/tts'),
    refresh: () => req('POST', '/models/refresh'),
  },

  // ── Skills ────────────────────────────────────────────────────────────────
  skills: {
    list: () => req<Skill[]>('GET', '/skills/'),
    get:  (id: string) => req<Skill>('GET', `/skills/${id}`),
  },
}

// ── WebSocket progress ────────────────────────────────────────────────────────
export function connectProgressWS(
  projectId: string,
  onMessage: (msg: ProgressMessage) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(`ws://localhost:7860/generation/ws/${projectId}`)
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch {}
  }
  ws.onclose = () => onClose?.()
  return ws
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface SystemStatus {
  hardware: {
    gpu_name: string
    vram_total_gb: number
    vram_free_mb: number
    vram_tier: string
    cpu_cores: number
    ram_total_gb: number
    platform: string
  }
  services: {
    ollama:  { running: boolean; url: string; models: unknown[] }
    comfyui: { running: boolean; url: string; path: string | null }
  }
}

export interface Project {
  id: string
  name: string
  topic: string
  script: string
  narration: string | null
  skill_id: string | null
  voice: string
  num_scenes: number
  status: 'idle' | 'queued' | 'running' | 'done' | 'error'
  created_at: string
  updated_at: string
  audio_duration: number | null
  final_path: string | null
  thumbnail_path: string | null
}

export interface ProjectCreate {
  name: string
  topic: string
  script: string
  voice?: string
  num_scenes?: number
  skill_id?: string | null
}

export interface Scene {
  id: string
  project_id: string
  index: number
  prompt: string | null
  status: 'pending' | 'generating' | 'done' | 'error' | 'locked'
  video_path: string | null
  thumbnail_path: string | null
  duration: number | null
  seed: number | null
  model_used: string | null
  error_message: string | null
}

export interface QueueItem {
  id: string
  project_id: string
  stage: string
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  progress: number
  eta_seconds: number | null
  created_at: string
  completed_at?: string
  error_message?: string
}

export interface ModelInfo {
  id: string
  name: string
  type: string
  source: string
  vram_required_mb: number
  size_mb: number
  installed: boolean
  capabilities: string[]
  description: string
}

export interface Skill {
  id: string
  name: string
  description: string
  voice: string
  voice_speed: number
  scene_pacing: string
  prompt_template: string
  aspect_ratio: string
  resolution: string
  subtitles: boolean
  music_mood: string
  post_processing: string[]
  icon: string
}

export interface RenderOpts {
  subtitles: boolean
  music: boolean
  interpolation: boolean
  upscaling: boolean
}

export interface ProgressMessage {
  project_id: string
  stage: string
  progress: number
  status: string
  message: string
  ping?: boolean
}
