@echo off
title Bank Locker OS - Backend Server
cd /d "%~dp0backend"
call .\venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
