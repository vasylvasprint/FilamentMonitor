@echo off
chcp 65001 > nul
echo Запуск FilamentMonitor...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run app.py --server.port 8501 --server.headless false
pause
