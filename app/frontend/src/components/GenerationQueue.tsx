import { useEffect } from 'react'
import { useQueueStore } from '@/stores/queueStore'
import { useProjectStore } from '@/stores/projectStore'
import { ProgressMessage } from '@/api/backend'

export default function GenerationQueue() {
  const { items, progress, fetchQueue, cancelItem } = useQueueStore()
  const { projects } = useProjectStore()

  useEffect(() => {
    fetchQueue()
    const interval = setInterval(fetchQueue, 5000)
    return () => clearInterval(interval)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Combine queue items with live progress
  const activeItems = items.filter((i) => i.status === 'queued' || i.status === 'running')

  if (activeItems.length === 0) return null

  return (
    <div className="border-t border-border-subtle bg-bg-surface px-4 py-2 flex gap-3 overflow-x-auto shrink-0">
      {activeItems.map((item) => {
        const proj = projects.find((p) => p.id === item.project_id)
        const live: ProgressMessage | undefined = progress[item.project_id]
        const pct = live ? live.progress : item.progress

        return (
          <div key={item.id}
            className="flex items-center gap-3 bg-bg-raised border border-border-subtle rounded-lg px-3 py-2 shrink-0 min-w-56 max-w-72"
          >
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-text-primary truncate">
                {proj?.name ?? item.project_id.slice(0, 8)}
              </div>
              <div className="text-xs text-text-muted truncate capitalize">
                {live?.stage?.replace(/_/g, ' ') ?? item.stage}
              </div>
              <div className="w-full bg-bg-muted rounded-full h-1 mt-1.5">
                <div
                  className="bg-accent h-1 rounded-full transition-all duration-500"
                  style={{ width: `${pct * 100}%` }}
                />
              </div>
            </div>
            <button
              className="text-text-disabled hover:text-error transition-colors text-xs shrink-0"
              onClick={() => cancelItem(item.id)}
              title="Cancel"
            >
              ✕
            </button>
          </div>
        )
      })}
    </div>
  )
}
