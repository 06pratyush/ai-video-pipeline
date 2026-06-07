@echo off
SETLOCAL

echo ============================================================
echo   AI Video Studio — Starting...
echo ============================================================

:: Check Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.10+ is required but not found on PATH.
    echo         Download it from https://python.org/downloads
    pause
    exit /b 1
)

:: Run system check
python installer\system_check.py >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] System check reported issues. Continuing anyway...
)

:: Bootstrap venv if not already done
IF NOT EXIST "app\runtime\python\Scripts\python.exe" (
    echo [SETUP] First run detected — installing dependencies...
    echo         This may take 5-15 minutes depending on your connection.
    python installer\bootstrap.py
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Bootstrap failed. Check the output above for details.
        pause
        exit /b 1
    )
)

:: Activate venv
SET VENV_PYTHON=app\runtime\python\Scripts\python.exe
IF NOT EXIST "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found at %VENV_PYTHON%
    pause
    exit /b 1
)

:: Start the backend daemon
echo [DAEMON] Starting backend on http://localhost:7860 ...
start /B "" "%VENV_PYTHON%" -m uvicorn app.backend.main:app --host 127.0.0.1 --port 7860

:: Wait for daemon to be ready
echo [DAEMON] Waiting for backend to initialize...
:wait_loop
timeout /t 2 /nobreak >nul
curl -s http://localhost:7860/system/health >nul 2>&1
IF %ERRORLEVEL% NEQ 0 goto wait_loop
echo [DAEMON] Backend ready.

:: Launch Electron frontend (if built)
IF EXIST "app\frontend\node_modules\.bin\electron.cmd" (
    echo [FRONTEND] Launching Electron app...
    cd app\frontend
    npx electron .
    cd ..\..
) ELSE IF EXIST "app\frontend\package.json" (
    echo [FRONTEND] Installing frontend dependencies...
    cd app\frontend
    call npm install
    echo [FRONTEND] Starting development server...
    call npm run dev
    cd ..\..
) ELSE (
    echo [INFO] No frontend found. Backend is running at http://localhost:7860
    echo        API docs: http://localhost:7860/docs
    pause
)

ENDLOCAL
