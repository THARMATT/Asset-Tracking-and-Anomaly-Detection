@echo off
REM =========================================================
REM  ONE-COMMAND STARTUP — Asset Tracking System (Windows)
REM  Opens two console windows: Flask backend + Vite frontend
REM =========================================================

echo.
echo  =========================================================
echo   IoT-Based Smart Asset Tracking and Anomaly Detection
echo  =========================================================

REM 1. Start Flask backend
start "Flask Backend (port 5000)" cmd /k "cd /d "%~dp0" && backend\venv\Scripts\activate.bat && python backend\app.py"

REM 2. Start Vite frontend
start "Vite Frontend (port 5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo  Flask API    --^>  http://127.0.0.1:5000/api/health
echo  Dashboard    --^>  http://localhost:5173
echo  IoT Status   --^>  http://127.0.0.1:5000/api/iot/status
echo  IoT Readings --^>  http://127.0.0.1:5000/api/iot/readings
echo.
echo  Close the two console windows to stop the services.
echo.
pause
