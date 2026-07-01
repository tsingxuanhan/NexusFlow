@echo off
chcp 936 >nul
title 铉枢·炉守 - 一键启动
echo.
echo   正在启动 PowerShell 脚本...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0start-hub.ps1"
