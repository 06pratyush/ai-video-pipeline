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

    // 'cancelled' is terminal too. Omitting it left the UI pinned to "running"
    // forever after a cancel, with the socket still open.
    if (msg.status === 'done' || msg.status === 'error' || msg.status === 'cancelled') {
      useProjectStore.getState().updateProjectLocally(msg.project_id, {
        status: msg.status,
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
