@echo off
setlocal
cd /d "%~dp0"
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Setup complete. Run run_dashboard.bat and run_mqtt_bridge.bat in separate terminals.
pause
