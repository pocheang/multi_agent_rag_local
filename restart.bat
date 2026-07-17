@echo off
set "ROOT=%~dp0"
echo Restarting QueryMind development stack through the canonical deployment entrypoint...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%deploy\scripts\deploy.ps1" -Environment development -Profile balanced %*
