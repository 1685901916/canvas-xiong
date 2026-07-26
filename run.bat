@echo off
cd /d "%~dp0"

echo Starting Infinite Canvas...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-canvas.ps1" -OpenWhenReady
if errorlevel 1 (
  echo.
  echo Canvas startup failed. See the error above.
  pause
  exit /b 1
)

echo Canvas is running at http://127.0.0.1:3001/
exit /b 0
