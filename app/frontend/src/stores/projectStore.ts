import { create } from 'zustand'
import { api, Project, Scene, ProjectCreate } from '@/api/backend'

interface ProjectStore {
  projects: Project[]
  activeProjectId: string | null
  scenes: Record<string, Scene[]>
  loading: boolean
  error: string | null

  fetchProjects: () => Promise<void>
  setActiveProject: (id: string | null) => void
  createProject: (data: ProjectCreate) => Promise<Project>
  updateProject: (id: string, data: Partial<ProjectCreate>) => Promise<void>
  deleteProject: (id: string) => Promise<void>
  fetchScenes: (projectId: string) => Promise<void>
  updateScene: (projectId: string, sceneId: string, data: Partial<Scene>) => Promise<void>
  updateProjectLocally: (id: string, patch: Partial<Project>) => void
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  activeProjectId: null,
  scenes: {},
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null })
    try {
      const projects = await api.projects.list()
      set({ projects, loading: false })
    } catch (e: unknown) {
      set({ error: String(e), loading: false })
    }
  },

  setActiveProject: (id) => {
    set({ activeProjectId: id })
    if (id) get().fetchScenes(id)
  },

  createProject: async (data) => {
    const project = await api.projects.create(data)
    set((s) => ({ projects: [project, ...s.projects] }))
    return project
  },

  updateProject: async (id, data) => {
    const updated = await api.projects.update(id, data)
    set((s) => ({
      projects: s.projects.map((p) => (p.id === id ? updated : p)),
    }))
  },

  deleteProject: async (id) => {
    await api.projects.delete(id)
    set((s) => ({
      projects: s.projects.filter((p) => p.id !== id),
      activeProjectId: s.activeProjectId === id ? null : s.activeProjectId,
    }))
  },

  fetchScenes: async (projectId) => {
    const scenes = await api.projects.scenes(projectId)
    set((s) => ({ scenes: { ...s.scenes, [projectId]: scenes } }))
  },

  updateScene: async (projectId, sceneId, data) => {
    const updated = await api.projects.updateScene(projectId, sceneId, data)
    set((s) => ({
      scenes: {
        ...s.scenes,
        [projectId]: (s.scenes[projectId] || []).map((sc) =>
          sc.id === sceneId ? updated : sc
        ),
      },
    }))
  },

  updateProjectLocally: (id, patch) => {
    set((s) => ({
      projects: s.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    }))
  },
}))

export const useActiveProject = () => {
  const { projects, activeProjectId } = useProjectStore()
  return projects.find((p) => p.id === activeProjectId) ?? null
}
