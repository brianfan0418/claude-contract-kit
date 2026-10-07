@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 22.12.0 or newer, then run npm install in this folder.
  pause
  exit /b 1
)
node start.mjs %1 --open
if errorlevel 1 pause
