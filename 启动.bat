@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d %~dp0
start "NexusFlow Server" python run.py
timeout /t 5 /nobreak >nul
start http://localhost:8900
exit
