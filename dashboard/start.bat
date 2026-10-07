@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 12 or newer, then run npm install in this folder.
  pause
  exit /b 1
)
node -e "if(parseInt(process.versions.node,10)<12){console.error('Install Node.js 12 or newer.');process.exit(1)}"
if errorlevel 1 (
  pause
  exit /b 1
)
node start.mjs %1 --open
if errorlevel 1 pause
