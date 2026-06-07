import { app, BrowserWindow, shell, ipcMain } from 'electron'
import { join } from 'path'
import { spawn, ChildProcess } from 'child_process'

const isDev = process.env.NODE_ENV === 'development'
let win: BrowserWindow | null = null
let daemonProcess: ChildProcess | null = null

function createWindow() {
  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#0a0a0b',
    titleBarStyle: 'hiddenInset',
    frame: process.platform !== 'win32',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  })

  if (isDev) {
    win.loadURL('http://localhost:5173')
    win.webContents.openDevTools({ mode: 'detach' })
  } else {
    win.loadFile(join(__dirname, '../dist/index.html'))
  }

  win.once('ready-to-show', () => win?.show())
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

async function startDaemon() {
  // In production, spawn the bundled Python backend
  if (isDev) return // dev: assume backend is already running

  const pythonBin = process.platform === 'win32'
    ? join(process.resourcesPath, 'runtime', 'python', 'Scripts', 'python.exe')
    : join(process.resourcesPath, 'runtime', 'python', 'bin', 'python')

  daemonProcess = spawn(pythonBin, ['-m', 'uvicorn', 'app.backend.main:app',
    '--host', '127.0.0.1', '--port', '7860'], {
    cwd: process.resourcesPath,
    stdio: 'ignore',
  })
}

function stopDaemon() {
  if (daemonProcess) {
    daemonProcess.kill()
    daemonProcess = null
  }
}

app.whenReady().then(async () => {
  await startDaemon()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopDaemon()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', stopDaemon)

// IPC: open native file dialog / shell reveal
ipcMain.handle('shell:open-path', (_e, path: string) => shell.openPath(path))
ipcMain.handle('shell:show-in-folder', (_e, path: string) => shell.showItemInFolder(path))
