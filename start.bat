@echo off
set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%deploy\scripts\deploy.ps1" -Environment development -Profile balanced %*
