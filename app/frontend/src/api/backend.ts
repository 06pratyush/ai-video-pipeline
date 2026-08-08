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

export const api = {
  // ── System ──────────────────────────────────────────────────────────────────
  system: {
    health:      () => req<{ status: string }>('GET', '/system/health'),
    status:      () => req<SystemStatus>('GET', '/system/status'),
    vram:        () => req<VramStatus>('GET', '/system/vram'),
    cacheStats:  () => req<{ total_entries: number; entries_with_hits: number }>('GET', '/system/cache'),
    clearCache:  () => req('DELETE', '/system/cache'),
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
    catalog: () => req<ModelCatalog>('GET', '/models/catalog'),
    installOllama: (id: string) => req<{ pulling: string; message: string }>('POST', `/models/install/ollama/${id}`),
  },

  // ── Skills ────────────────────────────────────────────────────────────────
  skills: {
    list: () => req<Skill[]>('GET', '/skills/'),
    get:  (id: string) => req<Skill>('GET', `/skills/${id}`),
  },

  // ── Templates ─────────────────────────────────────────────────────────────
  templates: {
    list:    () => req<Template[]>('GET', '/templates/'),
    get:     (id: string) => req<Template>('GET', `/templates/${id}`),
    create:  (data: TemplateCreate) => req<Template>('POST', '/templates/', data),
    update:  (id: string, data: Partial<TemplateCreate>) =>
      req<Template>('PATCH', `/templates/${id}`, data),
    delete:  (id: string) => req('DELETE', `/templates/${id}`),
    fromProject: (projectId: string, payload: { name: string; description?: string; include_script?: boolean; render_opts?: RenderOpts }) =>
      req<Template>('POST', `/templates/from-project/${projectId}`, payload),
    apply:   (id: string, payload: { project_name: string; topic: string; script?: string }) =>
      req<{ project: Project; template_render_opts: RenderOpts | null }>('POST', `/templates/${id}/apply`, payload),
  },

  // ── Versions ──────────────────────────────────────────────────────────────
  versions: {
    list:   (projectId: string) => req<ProjectVersion[]>('GET', `/projects/${projectId}/versions/`),
    create: (projectId: string, label?: string) =>
      req<ProjectVersion>('POST', `/projects/${projectId}/versions/`, { label }),
    restore: (projectId: string, versionId: string) =>
      // backup_version: the auto-snapshot taken of the pre-restore state, so the
      // UI can tell the user how to get their previous work back.
      req<{ restored: number; backup_version: number }>(
        'POST', `/projects/${projectId}/versions/${versionId}/restore`),
    delete: (projectId: string, versionId: string) =>
      req('DELETE', `/projects/${projectId}/versions/${versionId}`),
  },

  // ── Updates ───────────────────────────────────────────────────────────────
  updates: {
    check: () => req<UpdateCheck>('GET', '/updates/check'),
  },

  // ── Voices (cloning) ──────────────────────────────────────────────────────
  voices: {
    list:   () => req<{ xtts_available: boolean; voices: VoiceClip[] }>('GET', '/voices/'),
    delete: (id: string) => req('DELETE', `/voices/${id}`),
  },

  // ── Long-form ─────────────────────────────────────────────────────────────
  longform: {
    preview: (script: string, chunkWords?: number) =>
      req<LongFormPreview>('POST', '/longform/preview', { script, chunk_words: chunkWords ?? 180 }),
    create:  (payload: {
      base_name: string
      topic: string
      script: string
      voice?: string
      skill_id?: string | null
      chunk_words?: number
      render_opts?: RenderOpts
    }) => req<{ total_chunks: number; items: { project_id: string; queue_item_id: string; chunk_index: number; scene_count: number; est_seconds: number }[] }>(
      'POST', '/longform/create', payload,
    ),
  },

  // ── Skill import / export ─────────────────────────────────────────────────
  skillIO: {
    exportUrl: (id: string) => `${BASE}/skills/${id}/export`,
    import:    (skill: object) => req<Skill>('POST', '/skills/import', skill),
  },

  // ── Batch ─────────────────────────────────────────────────────────────────
  batch: {
    create: (items: BatchItem[], opts?: { template_id?: string; render_opts?: RenderOpts }) =>
      req<{ batch_size: number; items: { project_id: string; queue_item_id: string; name: string }[] }>(
        'POST', '/batch/',
        { items, template_id: opts?.template_id, render_opts: opts?.render_opts },
      ),
    status: () => req<{ queue_item_id: string; project_id: string; stage: string; status: string; progress: number }[]>(
      'GET', '/batch/',
    ),
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
  status: 'idle' | 'queued' | 'running' | 'done' | 'error' | 'cancelled'
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

export interface VramStatus {
  free_mb: number
  used_mb: number
  total_mb: number
  pct_used: number
}

export interface CatalogModel {
  id: string
  name: string
  type: string
  vram_required_mb: number
  size_gb: number
  quality_tier: string
  description: string
  compatible_skills: string[]
  install_method: string
  ollama_model?: string
  hf_repo?: string
  pip_package?: string
}

export interface ModelCatalog {
  version: string
  models: CatalogModel[]
}

export interface RenderOpts {
  subtitles: boolean
  music: boolean
  interpolation: boolean
  upscaling: boolean
}

export interface Template {
  id: string
  name: string
  description: string | null
  skill_id: string | null
  voice: string
  num_scenes: number
  script_seed: string | null
  render_opts: RenderOpts | null
  source_project_id: string | null
  use_count: number
  created_at: string
  updated_at: string
}

export interface TemplateCreate {
  name: string
  description?: string
  skill_id?: string | null
  voice?: string
  num_scenes?: number
  script_seed?: string
  render_opts?: RenderOpts | null
  source_project_id?: string
}

export interface ProjectVersion {
  id: string
  project_id: string
  version_num: number
  label: string | null
  snapshot: {
    name?: string
    topic?: string
    script?: string
    narration?: string | null
    skill_id?: string | null
    voice?: string
    num_scenes?: number
    audio_duration?: number | null
    render_opts?: RenderOpts
    scenes?: { index: number; prompt: string; seed: number | null; status: string }[]
  }
  final_path: string | null
  thumbnail: string | null
  duration: number | null
  created_at: string
}

export interface BatchItem {
  name: string
  topic: string
  script: string
  voice?: string
  num_scenes?: number
  skill_id?: string | null
}

export interface UpdateCheck {
  available: boolean
  current: string
  latest: string | null
  release_url?: string
  published_at?: string
  release_notes?: string
  downloads?: {
    windows?: string
    linux_appimage?: string
    linux_deb?: string
    macos_arm64?: string
    macos_x64?: string
  }
  error?: string
}

export interface VoiceClip {
  id: string
  name: string
  path: string
  size_kb: number
}

export interface LongFormChunk {
  index: number
  total: number
  script: string
  num_scenes: number
  est_duration_sec: number
}

export interface LongFormPreview {
  chunks: LongFormChunk[]
  total_chunks: number
  total_est_seconds: number
  needs_chunking: boolean
}

export interface ProgressMessage {
  project_id: string
  stage: string
  progress: number
  status: string
  message: string
  ping?: boolean
}
