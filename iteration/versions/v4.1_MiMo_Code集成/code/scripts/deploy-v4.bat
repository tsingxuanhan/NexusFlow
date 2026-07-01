@echo off
chcp 936 >nul 2>&1
title 铉枢·v4.0完整部署
echo ============================================
echo   铉枢·炉守 v4.0 物理本机部署
echo ============================================
echo.
echo 正在启动部署（需要管理员权限）...
powershell -ExecutionPolicy Bypass -Command "& {Start-Process PowerShell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0deploy-v4.ps1\"' -Verb RunAs}"
