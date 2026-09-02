[CmdletBinding()]
param(
    [ValidateSet("development", "test", "production")]
    [string]$Environment = "production",
    [ValidateSet("fast", "balanced", "deep")]
    [string]$Profile = "balanced",
    [switch]$Monitoring,
    [switch]$WithN8n
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$RuntimeEnv = Join-Path $Root ".runtime/$Environment.env"
$SecretsFile = Join-Path $Root ".runtime/generated-secrets.env"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required." }
if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { throw "Conda is required; activate or install rag-local." }
docker compose version | Out-Null

conda run --no-capture-output -n rag-local python (Join-Path $Root "deploy/scripts/config.py") render `
    --environment $Environment --profile $Profile --output $RuntimeEnv
if (-not (Test-Path -LiteralPath $SecretsFile)) { throw "Generated secret file was not created." }

$ComposeArgs = @(
    "--project-directory", $Root,
    "--project-name", "querymind",
    "--env-file", $RuntimeEnv,
    "-f", (Join-Path $Root "deploy/compose/compose.yaml")
)
if ($Environment -eq "development") {
    $ComposeArgs += @("-f", (Join-Path $Root "deploy/compose/compose.dev.yaml"))
}
if ($Environment -ne "development") {
    $ComposeArgs += @("-f", (Join-Path $Root "deploy/compose/compose.production.yaml"))
}
if ($Monitoring) {
    $ComposeArgs += @("-f", (Join-Path $Root "deploy/compose/compose.monitoring.yaml"))
}
if ($WithN8n) {
    $ComposeArgs += @("--profile", "with-n8n")
}

$env:RUNTIME_ENV_FILE = $RuntimeEnv
docker compose @ComposeArgs config -q
docker compose @ComposeArgs up -d --build
docker compose @ComposeArgs run --rm backend python deploy/scripts/init_app.py
docker compose @ComposeArgs exec -T backend python deploy/scripts/healthcheck.py

Write-Host "QueryMind deployed: environment=$Environment profile=$Profile"
if ($Environment -eq "development") {
    Write-Host "Frontend: http://127.0.0.1:5173"
} else {
    Write-Host "Frontend: http://127.0.0.1"
}
