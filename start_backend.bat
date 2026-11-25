@echo off
title SonoVoice Local Backend Server
echo Starting SonoVoice Local Backend and Reporting Service on http://127.0.0.1:8000 ...
cd /d "%~dp0"
set PYTHONPATH=%~dp0
call "%~dp0.venv\Scripts\uvicorn.exe" backend.app.main:app --host 127.0.0.1 --port 8000
pause
