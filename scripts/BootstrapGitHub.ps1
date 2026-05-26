<#
.SYNOPSIS
    Bootstrap a new PLATE repository using the GitHub CLI.

.DESCRIPTION
    Syncs canonical labels, removes conflicting default GitHub labels, replaces
    the CODEOWNERS placeholder, enables delete-branch-on-merge, applies
    conservative baseline branch protection, and optionally initializes the wiki.

    Requirements: gh (GitHub CLI) >= 2.x, git
    Works on Windows PowerShell 5.1+ and PowerShell Core (macOS, Linux).

.PARAMETER Repo
    GitHub repository in OWNER/REPO format (required).

.PARAMETER LocalRepo
    Path to the local repository checkout. Defaults to the current directory.

.PARAMETER OwnerHandle
    GitHub username or team handle for CODEOWNERS, e.g. @your-username.

.PARAMETER RemoveDefaultLabels
    Delete conflicting default GitHub labels.

.PARAMETER SetDeleteBranchOnMerge
    Enable delete-branch-on-merge.

.PARAMETER ProtectBranch
    Apply conservative baseline protection to the named branch.

.PARAMETER InitWiki
    Initialize the wiki with docs/wiki/Home.md.

.EXAMPLE
    .\BootstrapGitHub.ps1 -Repo owner/repo -OwnerHandle @your-handle `
        -RemoveDefaultLabels -SetDeleteBranchOnMerge -ProtectBranch main -InitWiki
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [string]$LocalRepo = ".",

    [string]$OwnerHandle = "",

    [switch]$RemoveDefaultLabels,

    [switch]$SetDeleteBranchOnMerge,

    [string]$ProtectBranch = "",

    [switch]$InitWiki
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultLabelsToRemove = @(
    "bug", "documentation", "duplicate", "enhancement",
    "good first issue", "help wanted", "invalid", "question", "wontfix"
)

$LocalRepo = (Resolve-Path $LocalRepo).Path
$LabelsPath = Join-Path $LocalRepo ".github" "labels.yml"

if (-not (Test-Path $LabelsPath)) {
    Write-Error "Label registry not found: $LabelsPath"
    exit 1
}

& gh auth status
if ($LASTEXITCODE -ne 0) { exit 1 }

function ConvertFrom-LabelsYml {
    param([string]$Path)
    $labels = [System.Collections.Generic.List[hashtable]]::new()
    $current = $null
    foreach ($rawLine in (Get-Content $Path -Encoding UTF8)) {
        $line = $rawLine.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        if ($line -match '^- name:\s*"?(.+?)"?\s*$') {
            if ($null -ne $current) { $labels.Add($current) }
            $current = @{ name = $Matches[1]; color = ""; description = "" }
        }
        elseif ($null -ne $current -and $line -match '^color:\s*"?(.+?)"?\s*$') {
            $current["color"] = $Matches[1]
        }
        elseif ($null -ne $current -and $line -match '^description:\s*"?(.+?)"?\s*$') {
            $current["description"] = $Matches[1]
        }
    }
    if ($null -ne $current) { $labels.Add($current) }
    return $labels
}

# Sync canonical labels ----------------------------------------------------------

Write-Host "Syncing canonical labels..."
$labels = ConvertFrom-LabelsYml -Path $LabelsPath
$labelCount = 0

# Fetch all existing labels once as a list of objects with actual and lower names.
$existingRaw = & gh label list --repo $Repo --limit 200 --json name | ConvertFrom-Json
$existingLabels = $existingRaw | ForEach-Object {
    [PSCustomObject]@{ actual = $_.name; lower = $_.name.ToLower() }
}

$canonicalNames = [System.Collections.Generic.List[string]]::new()

foreach ($label in $labels) {
    $canonicalNames.Add($label.name)
    $labelLower = $label.name.ToLower()
    $existing = $existingLabels | Where-Object { $_.lower -eq $labelLower } | Select-Object -First 1

    if ($existing) {
        & gh label edit $existing.actual `
            --repo $Repo `
            --name $label.name `
            --color $label.color `
            --description $label.description
    }
    else {
        & gh label create $label.name `
            --repo $Repo `
            --color $label.color `
            --description $label.description
    }
    $labelCount++
}

Write-Host "Synced $labelCount canonical labels."

# Remove default GitHub labels ---------------------------------------------------

if ($RemoveDefaultLabels) {
    $canonicalLower = $canonicalNames | ForEach-Object { $_.ToLower() }
    foreach ($defaultLabel in $DefaultLabelsToRemove) {
        if ($canonicalLower -contains $defaultLabel) { continue }
        $match = $existingLabels | Where-Object { $_.lower -eq $defaultLabel } | Select-Object -First 1
        if ($match) {
            & gh label delete $match.actual --repo $Repo --yes
        }
    }
    Write-Host "Removed conflicting default GitHub labels."
}

# Replace CODEOWNERS placeholder -------------------------------------------------

if ($OwnerHandle -ne "") {
    $codeownersPath = Join-Path $LocalRepo ".github" "CODEOWNERS"
    if (Test-Path $codeownersPath) {
        $content = Get-Content $codeownersPath -Raw -Encoding UTF8
        if ($content -match "@PLATE_REPO_OWNER") {
            $updated = $content.Replace("@PLATE_REPO_OWNER", $OwnerHandle)
            [System.IO.File]::WriteAllText($codeownersPath, $updated, [System.Text.Encoding]::UTF8)
            Write-Host "Updated .github/CODEOWNERS with the provided owner handle."
        }
        else {
            Write-Host ".github/CODEOWNERS already uses the requested owner handle."
        }
    }
}

# Enable delete-branch-on-merge --------------------------------------------------

if ($SetDeleteBranchOnMerge) {
    & gh repo edit $Repo --delete-branch-on-merge
    Write-Host "Enabled delete-branch-on-merge."
}

# Apply baseline branch protection -----------------------------------------------

if ($ProtectBranch -ne "") {
    $protectionJson = '{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}'
    $tmpFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tmpFile, $protectionJson, [System.Text.Encoding]::UTF8)
        & gh api `
            --method PUT `
            -H "Accept: application/vnd.github+json" `
            "repos/$Repo/branches/$ProtectBranch/protection" `
            --input $tmpFile
    }
    finally {
        Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Applied baseline protection to $ProtectBranch."
}

# Initialize wiki ----------------------------------------------------------------

if ($InitWiki) {
    $wikiSource = Join-Path $LocalRepo "docs" "wiki" "Home.md"
    if (-not (Test-Path $wikiSource)) {
        Write-Error "Wiki source file not found: $wikiSource"
        exit 1
    }

    $user = (& gh api user | ConvertFrom-Json)
    $authorName  = if ($user.name)  { $user.name }  else { $user.login }
    $authorEmail = if ($user.email) { $user.email } else { "$($user.login)@users.noreply.github.com" }
    $token = (& gh auth token)

    $wikiDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $wikiDir | Out-Null
    try {
        $cloneUrl = "https://github.com/${Repo}.wiki.git"
        $askpassFile = Join-Path ([System.IO.Path]::GetTempPath()) ("git-askpass-" + [System.IO.Path]::GetRandomFileName())
        try {
            if ($env:OS -eq "Windows_NT") {
                $askpassFile += ".cmd"
                Set-Content -Path $askpassFile -Value "@echo off`r`necho $token" -NoNewline
            } else {
                Set-Content -Path $askpassFile -Value "#!/bin/sh`necho '$token'" -NoNewline
                & chmod +x $askpassFile
            }
            $env:GIT_ASKPASS = $askpassFile
            $env:GIT_TERMINAL_PROMPT = "0"
            & git -c credential.helper= clone $cloneUrl $wikiDir
            if ($LASTEXITCODE -ne 0) { throw "git clone failed (exit code $LASTEXITCODE). Is the wiki enabled on the repository?" }

            Copy-Item $wikiSource -Destination (Join-Path $wikiDir "Home.md") -Force

            $status = & git -C $wikiDir status --short
            if (-not $status) {
                Write-Host "Wiki homepage was already up to date."
            }
            else {
                & git -C $wikiDir config user.name  $authorName
                & git -C $wikiDir config user.email $authorEmail
                & git -C $wikiDir add Home.md
                & git -C $wikiDir commit -m "docs: initialize wiki home page"
                & git -c credential.helper= -C $wikiDir push origin master
                Write-Host "Initialized the wiki homepage from docs/wiki/Home.md."
            }
        } finally {
            Remove-Item $askpassFile -Force -ErrorAction SilentlyContinue
            Remove-Item env:\GIT_ASKPASS -ErrorAction SilentlyContinue
            Remove-Item env:\GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue
        }
    }
    finally {
        Remove-Item $wikiDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Manual follow-up ---------------------------------------------------------------

Write-Host ""
Write-Host "Manual follow-up still required:"
Write-Host "1. Replace placeholder product language in SPEC.md, CURRENT.md, and public-facing docs."
Write-Host "2. Decide whether branch protection should also require approvals, code-owner review, status checks, or linear history."
Write-Host "3. Configure GitHub Projects fields for planning state such as status, priority, owner, iteration, target date, and release target."
Write-Host "4. Create real Epic: short-name labels and the first Epic issue."
Write-Host "5. Tune CI, release, pages, and audit workflows for the project stack."
Write-Host "6. Decide whether to enable wiki sync and, if so, create PLATE_WIKI_SYNC_ENABLED and WIKI_TOKEN."
