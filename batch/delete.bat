@echo off
chcp 65001 >nul

REM Папка, где лежит этот .bat
set "ROOT=%~dp0"

REM Удаляем и пересоздаём нужные папки
rmdir /S /Q "%ROOT%англ"
mkdir "%ROOT%англ"

rmdir /S /Q "%ROOT%англ + рус"
mkdir "%ROOT%англ + рус"

rmdir /S /Q "%ROOT%рус"
mkdir "%ROOT%рус"