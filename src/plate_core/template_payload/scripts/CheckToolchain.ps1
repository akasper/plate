[CmdletBinding()]
param(
    [string]$Root = "."
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path $Root).Path
$missing = [System.Collections.Generic.List[string]]::new()

function Test-RequiredTool {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$Reason
    )

    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        $missing.Add("$Command|$Reason")
    }
}

Test-RequiredTool -Command "gh" -Reason "required for repository bootstrap and GitHub automation"
Test-RequiredTool -Command "git" -Reason "required for repository bootstrap and wiki initialization"

if (Test-Path (Join-Path $Root "package.json")) {
    Test-RequiredTool -Command "node" -Reason "required because package.json is present"
    Test-RequiredTool -Command "npm" -Reason "required because package.json is present"
}

if (Test-Path (Join-Path $Root "pnpm-lock.yaml")) {
    Test-RequiredTool -Command "node" -Reason "required because pnpm-lock.yaml is present"
    Test-RequiredTool -Command "pnpm" -Reason "required because pnpm-lock.yaml is present"
}

if (Test-Path (Join-Path $Root "yarn.lock")) {
    Test-RequiredTool -Command "node" -Reason "required because yarn.lock is present"
    Test-RequiredTool -Command "yarn" -Reason "required because yarn.lock is present"
}

if (Test-Path (Join-Path $Root "wally.toml")) {
    Test-RequiredTool -Command "wally" -Reason "required because wally.toml is present"
}

if ((Test-Path (Join-Path $Root "default.project.json")) -or (Test-Path (Join-Path $Root "rojo.json"))) {
    Test-RequiredTool -Command "rojo" -Reason "required because Rojo project metadata is present"
}

if ($missing.Count -gt 0) {
    Write-Host "Missing required tools for this repository:"
    foreach ($item in $missing) {
        $parts = $item.Split("|", 2)
        Write-Host "  - $($parts[0]) ($($parts[1]))"
    }
    exit 1
}

Write-Host "Toolchain preflight passed."
