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

Write-Host "PLATE repository validation passed."
