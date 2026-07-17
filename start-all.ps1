[CmdletBinding()]
param(
    [ValidateSet("fast", "balanced", "deep")]
    [string]$Profile = "balanced"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot ".")).Path
& (Join-Path $Root "deploy/scripts/deploy.ps1") -Environment development -Profile $Profile
