[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { throw "Conda is required; install or activate rag-local." }
conda run --no-capture-output -n rag-local python -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
