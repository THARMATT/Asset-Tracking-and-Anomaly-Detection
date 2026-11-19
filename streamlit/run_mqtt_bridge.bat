@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" mqtt_bridge.py
