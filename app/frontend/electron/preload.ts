import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  // Shell helpers
  openPath:     (path: string) => ipcRenderer.invoke('shell:open-path', path),
  showInFolder: (path: string) => ipcRenderer.invoke('shell:show-in-folder', path),
  platform:     process.platform,

  // Setup / bootstrap
  startSetup: () => ipcRenderer.invoke('setup:start'),
  onSetupNeeded: (cb: (needed: boolean) => void) => {
    const handler = (_: Electron.IpcRendererEvent, needed: boolean) => cb(needed)
    ipcRenderer.on('setup:needed', handler)
    return () => ipcRenderer.removeListener('setup:needed', handler)
  },
  onSetupMessage: (cb: (msg: unknown) => void) => {
    const handler = (_: Electron.IpcRendererEvent, msg: unknown) => cb(msg)
    ipcRenderer.on('setup:message', handler)
    return () => ipcRenderer.removeListener('setup:message', handler)
  },
})
