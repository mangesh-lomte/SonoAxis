@echo off
title SonoVoice Automated Test Suite
echo Running SonoVoice Full Automated Test Suite (Speech + Structuring + Persistence)...
cd /d "%~dp0"
set PYTHONPATH=%~dp0
call "%~dp0.venv\Scripts\pytest.exe" -v tests
pause
