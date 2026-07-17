[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "frontend")
if (-not (Test-Path -LiteralPath "node_modules")) {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
}
npm run dev
