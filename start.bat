@echo off
SETLOCAL EnableDelayedExpansion
TITLE AI Video Studio

echo.
echo ============================================================
echo   AI Video Studio
echo ============================================================
echo.

:: ── Locate project root ────────────────────────────────────────────────────────
SET "ROOT=%~dp0"
IF "%ROOT:~-1%"=="\" SET "ROOT=%ROOT:~0,-1%"

:: ── Check Python ───────────────────────────────────────────────────────────────
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.10+ is required but was not found on PATH.
    echo.
    echo         Download it from: https://python.org/downloads
    echo         Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: ── Check Node.js ──────────────────────────────────────────────────────────────
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Node.js not found. The GUI requires Node.js 18+.
    echo           Download from: https://nodejs.org
    echo           The backend API will still work at http://localhost:7860
    echo.
)

:: ── Determine venv python path ─────────────────────────────────────────────────
SET "VENV_PYTHON=%ROOT%\app\runtime\python\Scripts\python.exe"
SET "SETUP_NEEDED=0"
IF NOT EXIST "%VENV_PYTHON%" SET "SETUP_NEEDED=1"

:: ── First run: run bootstrap INSIDE the Electron window ───────────────────────
:: The Electron app detects needsSetup() and shows SetupScreen, which communicates
:: with bootstrap.py via IPC. We just need to launch the app.
::
:: If Node/Electron is not available, fall back to console bootstrap.
node --version >nul 2>&1
SET "HAS_NODE=%ERRORLEVEL%"

IF %SETUP_NEEDED%==1 (
    IF %HAS_NODE% NEQ 0 (
        echo [SETUP] Running headless bootstrap (no Node.js for GUI)...
        echo         This may take 10-20 minutes on first run.
        echo.
        python "%ROOT%\installer\bootstrap.py"
        IF %ERRORLEVEL% NEQ 0 (
            echo.
            echo [ERROR] Setup failed. Check the output above.
            pause
            exit /b 1
        )
    )
)

:: ── Start backend daemon ───────────────────────────────────────────────────────
IF EXIST "%VENV_PYTHON%" (
    echo [DAEMON] Starting backend on http://localhost:7860 ...
    START /B "" "%VENV_PYTHON%" -m uvicorn app.backend.main:app --host 127.0.0.1 --port 7860 2>nul
    echo [DAEMON] Backend starting in background...
    timeout /t 3 /nobreak >nul
)

:: ── Launch Electron / Vite dev ────────────────────────────────────────────────
SET "FRONTEND=%ROOT%\app\frontend"

:: Production: packaged Electron
IF EXIST "%FRONTEND%\release\win-unpacked\AI Video Studio.exe" (
    START "" "%FRONTEND%\release\win-unpacked\AI Video Studio.exe"
    goto :end
)

:: Dev: npm run dev (Vite + Electron)
IF EXIST "%FRONTEND%\node_modules\.bin\electron.cmd" (
    echo [FRONTEND] Launching Electron dev mode...
    cd /d "%FRONTEND%"
    SET "NODE_ENV=development"
    START "" cmd /c "npx electron . 2>nul"
    cd /d "%ROOT%"
    goto :end
)

:: Fallback: just Vite (browser)
IF EXIST "%FRONTEND%\node_modules\.bin\vite.cmd" (
    echo [FRONTEND] Starting browser dev server at http://localhost:5173 ...
    cd /d "%FRONTEND%"
    START "" cmd /c "npx vite 2>nul"
    cd /d "%ROOT%"
    timeout /t 3 /nobreak >nul
    start http://localhost:5173
    goto :end
)

:: No frontend built at all
echo [INFO] Frontend not built. Installing dependencies...
cd /d "%FRONTEND%"
call npm install
echo [INFO] Starting dev server...
START "" cmd /c "npx vite 2>nul"
cd /d "%ROOT%"
timeout /t 3 /nobreak >nul
start http://localhost:5173

:end
echo.
echo [OK] AI Video Studio is running.
echo      Backend API: http://localhost:7860
echo      API docs:    http://localhost:7860/docs
echo.
ENDLOCAL
