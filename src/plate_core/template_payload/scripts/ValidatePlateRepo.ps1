[CmdletBinding()]
param(
    [string]$Root = "."
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path $Root).Path

$requiredFiles = @(
    "AGENTS.md",
    "CURRENT.md",
    "SPEC.md",
    ".agentic/process.yml",
    ".agentic/skills.yml",
    ".github/copilot-instructions.md",
    ".github/workflows/ci.yml"
)

foreach ($rel in $requiredFiles) {
    $full = Join-Path $Root $rel
    if (-not (Test-Path $full)) {
        Write-Error "Required artifact is missing: $rel"
        exit 1
    }
}

$ciFile = Join-Path $Root ".github/workflows/ci.yml"
$copilotFile = Join-Path $Root ".github/copilot-instructions.md"
$currentFile = Join-Path $Root "CURRENT.md"

$runtimeManifests = @(
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "wally.toml",
    "default.project.json",
    "rojo.json"
)

$hasRuntime = $false
foreach ($manifest in $runtimeManifests) {
    if (Test-Path (Join-Path $Root $manifest)) {
        $hasRuntime = $true
        break
    }
}

if ($hasRuntime) {
    if (Select-String -Path $ciFile -Pattern 'echo "Tests would run here"' -Quiet) {
        Write-Error "Runtime manifest detected, but CI still uses placeholder test command."
        exit 1
    }

    if (Select-String -Path $copilotFile -Pattern 'does not define a local build, lint, or test toolchain yet' -Quiet -CaseSensitive:$false) {
        Write-Error "Runtime manifest detected, but .github/copilot-instructions.md still claims no concrete toolchain."
        exit 1
    }

    if (Select-String -Path $currentFile -Pattern 'Project-specific CI commands are not defined by the generic template' -Quiet -CaseSensitive:$false) {
        Write-Error "Runtime manifest detected, but CURRENT.md still records missing project-specific CI commands."
        exit 1
    }
}

function Get-PlatePlatform {
    param([string]$Root)
    $path = Join-Path $Root ".plate"
    if (-not (Test-Path -LiteralPath $path)) {
        return "posix"
    }
    try {
        $raw = Get-Content -LiteralPath $path -Raw -ErrorAction Stop
        $data = $raw | ConvertFrom-Json
    } catch {
        Write-Error "invalid JSON in .plate: $($_.Exception.Message)"
        exit 1
    }
    if ($null -eq $data -or -not ($data -is [System.Management.Automation.PSCustomObject] -or $data -is [hashtable])) {
        Write-Error ".plate must contain a top-level object"
        exit 1
    }
    $value = $null
    if ($data.PSObject.Properties.Name -contains "platform") {
        $value = $data.platform
    }
    # A missing key or JSON null means posix. Empty string is not a platform.
    if ($null -eq $value) {
        return "posix"
    }
    $allowed = @("posix", "posix-and-windows", "windows")
    if ($allowed -notcontains [string]$value) {
        Write-Error "invalid platform: $value (allowed: posix, posix-and-windows, windows)"
        exit 1
    }
    return [string]$value
}

function Test-PlateScript {
    param([string]$Root, [string]$Name)
    $direct = Join-Path $Root (Join-Path "scripts" $Name)
    $namespaced = Join-Path $Root (Join-Path "scripts" (Join-Path "plate" $Name))
    return (Test-Path -LiteralPath $direct) -or (Test-Path -LiteralPath $namespaced)
}

$platePlatform = Get-PlatePlatform -Root $Root
switch ($platePlatform) {
    "posix" { $gifChecks = @("gif-from-video.sh") }
    "windows" { $gifChecks = @("gif-from-video.ps1") }
    "posix-and-windows" { $gifChecks = @("gif-from-video.sh", "gif-from-video.ps1") }
    default {
        Write-Error "invalid platform: $platePlatform"
        exit 1
    }
}
foreach ($name in $gifChecks) {
    if (-not (Test-PlateScript -Root $Root -Name $name)) {
        Write-Error "Required script is missing for platform ${platePlatform}: scripts/$name"
        exit 1
    }
}

Write-Host "PLATE repository validation passed."
