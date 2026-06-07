import { create } from 'zustand'
import { api, ModelInfo, Skill, SystemStatus } from '@/api/backend'

interface ModelStore {
  models: ModelInfo[]
  skills: Skill[]
  systemStatus: SystemStatus | null
  daemonReady: boolean
  loading: boolean

  checkDaemon: () => Promise<boolean>
  fetchAll: () => Promise<void>
  fetchSkills: () => Promise<void>
  fetchStatus: () => Promise<void>
}

export const useModelStore = create<ModelStore>((set) => ({
  models: [],
  skills: [],
  systemStatus: null,
  daemonReady: false,
  loading: false,

  checkDaemon: async () => {
    try {
      await api.system.health()
      set({ daemonReady: true })
      return true
    } catch {
      set({ daemonReady: false })
      return false
    }
  },

  fetchAll: async () => {
    set({ loading: true })
    try {
      const [models, skills, status] = await Promise.all([
        api.models.all(),
        api.skills.list(),
        api.system.status(),
      ])
      set({ models, skills, systemStatus: status, loading: false, daemonReady: true })
    } catch {
      set({ loading: false })
    }
  },

  fetchSkills: async () => {
    const skills = await api.skills.list()
    set({ skills })
  },

  fetchStatus: async () => {
    try {
      const status = await api.system.status()
      set({ systemStatus: status })
    } catch {}
  },
}))
