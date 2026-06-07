import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  openPath:       (path: string) => ipcRenderer.invoke('shell:open-path', path),
  showInFolder:   (path: string) => ipcRenderer.invoke('shell:show-in-folder', path),
  platform:       process.platform,
})
