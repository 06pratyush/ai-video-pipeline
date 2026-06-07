import { app, BrowserWindow, shell, ipcMain } from 'electron'
import { join, resolve } from 'path'
import { spawn, ChildProcess } from 'child_process'
import { existsSync } from 'fs'
import { platform } from 'os'

const isDev = process.env.NODE_ENV === 'development'
let win: BrowserWindow | null = null
let daemonProcess: ChildProcess | null = null
let bootstrapProcess: ChildProcess | null = null

// ── Setup detection ────────────────────────────────────────────────────────────
function needsSetup(): boolean {
  const root = isDev
    ? resolve(__dirname, '../../..')
    : resolve(process.resourcesPath)

  const venvPython = platform() === 'win32'
    ? join(root, 'app', 'runtime', 'python', 'Scripts', 'python.exe')
    : join(root, 'app', 'runtime', 'python', 'bin', 'python')

  return !existsSync(venvPython)
}

// ── Window ─────────────────────────────────────────────────────────────────────
function createWindow(setupMode = false) {
  win = new BrowserWindow({
    width:  setupMode ? 860 : 1400,
    height: setupMode ? 560 : 900,
    minWidth:  setupMode ? 720 : 1024,
    minHeight: setupMode ? 480 : 700,
    backgroundColor: '#0a0a0b',
    titleBarStyle: 'hiddenInset',
    frame: process.platform !== 'win32',
    resizable: true,
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  })

  if (isDev) {
    win.loadURL('http://localhost:5173')
    // Only open DevTools in dev when not in setup mode
    // win.webContents.openDevTools({ mode: 'detach' })
  } else {
    win.loadFile(join(__dirname, '../dist/index.html'))
  }

  win.once('ready-to-show', () => win?.show())
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// ── Bootstrap IPC ─────────────────────────────────────────────────────────────
function startBootstrap() {
  const root = isDev
    ? resolve(__dirname, '../../..')
    : resolve(process.resourcesPath)

  const bootstrapScript = join(root, 'installer', 'bootstrap.py')
  const python = process.platform === 'win32'
    ? 'python'
    : 'python3'

  bootstrapProcess = spawn(python, [bootstrapScript], {
    cwd: root,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  bootstrapProcess.stdout?.setEncoding('utf8')
  bootstrapProcess.stderr?.setEncoding('utf8')

  let buffer = ''
  bootstrapProcess.stdout?.on('data', (chunk: string) => {
    buffer += chunk
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        const msg = JSON.parse(trimmed)
        win?.webContents.send('setup:message', msg)
        // When complete, resize window and start daemon
        if (msg.step === 'complete') {
          win?.setSize(1400, 900)
          win?.setMinimumSize(1024, 700)
          startDaemon()
        }
      } catch {
        // Not JSON — send as log line
        win?.webContents.send('setup:message', { step: 'log', message: trimmed })
      }
    }
  })

  bootstrapProcess.stderr?.on('data', (chunk: string) => {
    for (const line of chunk.split('\n').filter(Boolean)) {
      win?.webContents.send('setup:message', { step: 'log', message: `[stderr] ${line}` })
    }
  })

  bootstrapProcess.on('exit', (code) => {
    if (code !== 0) {
      win?.webContents.send('setup:message', {
        step: 'fatal',
        message: `Bootstrap exited with code ${code}`,
      })
    }
  })
}

ipcMain.handle('setup:start', () => {
  startBootstrap()
})

// ── Daemon ────────────────────────────────────────────────────────────────────
async function startDaemon() {
  if (isDev) return  // dev: assume backend already running via start.bat

  const root = process.resourcesPath
  const pythonBin = process.platform === 'win32'
    ? join(root, 'app', 'runtime', 'python', 'Scripts', 'python.exe')
    : join(root, 'app', 'runtime', 'python', 'bin', 'python')

  if (!existsSync(pythonBin)) return

  daemonProcess = spawn(
    pythonBin,
    ['-m', 'uvicorn', 'app.backend.main:app', '--host', '127.0.0.1', '--port', '7860'],
    { cwd: root, stdio: 'ignore' }
  )
}

function stopDaemon() {
  daemonProcess?.kill()
  daemonProcess = null
  bootstrapProcess?.kill()
  bootstrapProcess = null
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  const setupMode = needsSetup()
  createWindow(setupMode)

  // Tell renderer whether setup is needed
  win?.webContents.once('did-finish-load', () => {
    win?.webContents.send('setup:needed', setupMode)
    if (!setupMode && !isDev) {
      startDaemon()
    }
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopDaemon()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', stopDaemon)

// ── Shell IPC ──────────────────────────────────────────────────────────────────
ipcMain.handle('shell:open-path',      (_e, path: string) => shell.openPath(path))
ipcMain.handle('shell:show-in-folder', (_e, path: string) => shell.showItemInFolder(path))
