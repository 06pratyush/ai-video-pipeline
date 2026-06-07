import { create } from 'zustand'
import { api, QueueItem, ProgressMessage, RenderOpts, connectProgressWS } from '@/api/backend'
import { useProjectStore } from './projectStore'

interface QueueStore {
  items: QueueItem[]
  progress: Record<string, ProgressMessage>
  sockets: Record<string, WebSocket>

  fetchQueue: () => Promise<void>
  startGeneration: (projectId: string, renderOpts?: RenderOpts) => Promise<void>
  cancelItem: (queueItemId: string) => Promise<void>
  subscribeToProject: (projectId: string) => void
  unsubscribeFromProject: (projectId: string) => void
  handleProgress: (msg: ProgressMessage) => void
}

export const useQueueStore = create<QueueStore>((set, get) => ({
  items: [],
  progress: {},
  sockets: {},

  fetchQueue: async () => {
    const items = await api.generation.queue()
    set({ items })
  },

  startGeneration: async (projectId: string, renderOpts?: RenderOpts) => {
    await api.generation.start(projectId, renderOpts)
    useProjectStore.getState().updateProjectLocally(projectId, { status: 'queued' })
    get().subscribeToProject(projectId)
    get().fetchQueue()
  },

  cancelItem: async (queueItemId: string) => {
    await api.generation.cancel(queueItemId)
    get().fetchQueue()
  },

  subscribeToProject: (projectId: string) => {
    if (get().sockets[projectId]) return
    const ws = connectProgressWS(
      projectId,
      (msg) => get().handleProgress(msg),
      () => {
        set((s) => {
          const sockets = { ...s.sockets }
          delete sockets[projectId]
          return { sockets }
        })
      }
    )
    set((s) => ({ sockets: { ...s.sockets, [projectId]: ws } }))
  },

  unsubscribeFromProject: (projectId: string) => {
    const ws = get().sockets[projectId]
    if (ws) {
      ws.close()
      set((s) => {
        const sockets = { ...s.sockets }
        delete sockets[projectId]
        return { sockets }
      })
    }
  },

  handleProgress: (msg: ProgressMessage) => {
    if (msg.ping) return
    set((s) => ({ progress: { ...s.progress, [msg.project_id]: msg } }))

    if (msg.status === 'done' || msg.status === 'error') {
      useProjectStore.getState().updateProjectLocally(msg.project_id, {
        status: msg.status === 'done' ? 'done' : 'error',
      })
      if (msg.status === 'done') {
        useProjectStore.getState().fetchProjects()
      }
      get().unsubscribeFromProject(msg.project_id)
    } else {
      useProjectStore.getState().updateProjectLocally(msg.project_id, { status: 'running' })
    }
  },
}))
