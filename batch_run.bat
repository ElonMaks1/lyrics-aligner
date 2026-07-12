@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Batch Lyrics Align (HQ, line timings)
echo ========================================
echo.
echo Input:  batch\англ  batch\рус  batch\англ + рус
echo Output: batch_output\lines\  (only .lines.json)
echo.

.\.venv\Scripts\python.exe scripts\batch_align.py
echo.
pause
