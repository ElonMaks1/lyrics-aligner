@echo off
cd /d "%~dp0"
echo Downloading Demucs models (required once, ~80 MB each)...
.\.venv\Scripts\pip.exe install requests -q
.\.venv\Scripts\python.exe scripts\download_models.py htdemucs htdemucs_ft
pause
