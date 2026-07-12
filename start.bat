@echo off
cd /d "%~dp0"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr LISTENING') do (
  echo Stopping old server PID %%a...
  taskkill /F /PID %%a >nul 2>&1
)

timeout /t 1 /nobreak >nul
.\.venv\Scripts\python.exe run.py
