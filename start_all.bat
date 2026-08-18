@echo off
title Bank Locker OS - Complete System Launcher
echo ===================================================
echo Starting Bank Locker OS (Backend + Operator Portal)
echo ===================================================

start "Bank Locker OS - Backend" "%~dp0run_backend.bat"
start "Bank Locker OS - Operator Portal" "%~dp0run_frontend.bat"

echo.
echo Both servers are starting up!
echo Backend: http://localhost:8000 (API Docs: http://localhost:8000/docs)
echo Portal:  http://localhost:3000
echo.
