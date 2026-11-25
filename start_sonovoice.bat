@echo off
title SonoVoice — Clinical Ultrasound Intelligence
setlocal enabledelayedexpansion

echo ==================================================================
echo                  SONOVOICE CLINICAL SUITE
echo       100%% Local, Zero-Cost Ultrasound Documentation
echo ==================================================================
echo.

cd /d "%~dp0"
set PYTHONPATH=%~dp0
set VENV_UVICORN=%~dp0.venv\Scripts\uvicorn.exe

if not exist "%VENV_UVICORN%" (
    echo [ERROR] Virtual environment not found at %~dp0.venv
    echo Please ensure dependencies are installed via requirements.txt
    pause
    exit /b 1
)

:: Check if port 8000 is already active to prevent duplicate instances
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] SonoVoice service is already running on port 8000.
    echo [INFO] Opening application in your default browser...
    start http://127.0.0.1:8000/
    echo.
    echo Application running at: http://127.0.0.1:8000/
    echo Press any key to exit this launcher window...
    pause >nul
    exit /b 0
)

echo [INFO] Starting SonoVoice unified server on http://127.0.0.1:8000 ...
echo [INFO] Serving compiled production React frontend and local AI backend...
echo.

start "SonoVoice Server" /min "%VENV_UVICORN%" backend.app.main:app --host 127.0.0.1 --port 8000

:: Wait 2 seconds for server socket bind
timeout /t 2 /nobreak >nul

echo [INFO] Launching browser to http://127.0.0.1:8000/ ...
start http://127.0.0.1:8000/

echo.
echo ==================================================================
echo SonoVoice is running at: http://127.0.0.1:8000/
echo To stop the server, close the minimized 'SonoVoice Server' window.
echo ==================================================================
echo.
pause
