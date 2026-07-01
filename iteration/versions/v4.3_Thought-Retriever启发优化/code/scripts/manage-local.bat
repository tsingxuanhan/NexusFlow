@echo off
chcp 936 >nul 2>&1
title 铉枢·本地部署管理
echo 正在启动部署管理器...
powershell -ExecutionPolicy Bypass -File "%~dp0manage-local.ps1"
