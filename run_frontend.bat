@echo off
title Bank Locker OS - Operator Portal
cd /d "%~dp0admin-web"
npm run dev -- --port 3000 --host 0.0.0.0
pause
