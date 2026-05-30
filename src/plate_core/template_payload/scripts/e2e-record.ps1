# e2e-record.ps1 - Record Playwright E2E tests locally with optional demo GIF generation
# Supports Windows (PowerShell 5.1+)
#
# Usage: .\scripts\e2e-record.ps1 -TestName "login" [-Headed] [-Debug] [-Quality medium]
#
# Parameters:
#   -TestName          Name or pattern of the test to record (required)
#   -Headed            Run test in headed mode (visible browser window)
#   -Debug             Enable Playwright Inspector for debugging
#   -Quality           GIF quality if generating GIF: high, medium, or low (default: medium)
#   -SkipGif           Don't offer to generate GIF (just record video)
#   -Help              Show this help message

param(
    [Parameter(Position=0, HelpMessage="Name or pattern of the test to record")]
    [string]$TestName = "",
    
    [switch]$Headed,
    [switch]$Debug,
    
    [Parameter(HelpMessage="GIF quality: high, medium, or low")]
    [ValidateSet("high", "medium", "low")]
    [string]$Quality = "medium",
    
    [switch]$SkipGif,
    [switch]$Help
)

# Helper functions for colored output
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "   $Message" -ForegroundColor Cyan
}

# Show help
if ($Help -or [string]::IsNullOrWhiteSpace($TestName)) {
    $helpText = @"
e2e-record.ps1 - Record Playwright E2E tests with optional GIF generation

USAGE:
    .\scripts\e2e-record.ps1 -TestName <name> [options]

PARAMETERS:
    -TestName <string>
        Name or pattern of the test to record
        Required. Matches Playwright test name.

    -Headed
        Run test in headed mode (visible browser window)
        Default: headless

    -Debug
        Enable Playwright Inspector for debugging
        Default: disabled

    -Quality <string>
        GIF quality if generating GIF
        Options: high, medium, low (default: medium)

    -SkipGif
        Don't offer to generate GIF (just record video)
        Default: offer to generate

    -Help
        Display this help message

EXAMPLES:
    # Record a test in headless mode
    .\scripts\e2e-record.ps1 -TestName "login"

    # Record with visible browser
    .\scripts\e2e-record.ps1 -TestName "user creation" -Headed

    # Record with debugger
    .\scripts\e2e-record.ps1 -TestName "checkout" -Debug

    # Record and generate low-quality GIF
    .\scripts\e2e-record.ps1 -TestName "homepage" -Quality low

ENVIRONMENT VARIABLES:
    PLAYWRIGHT_HEADED    Set to 1 for headed mode (overridable by -Headed flag)
    PLAYWRIGHT_DEBUG     Set to 1 for debug mode
    CI                   If set, assumes CI environment and skips interactive prompts

DEPENDENCIES:
    - Node.js 18+
    - npm
    - Playwright (installed via npm)
    - ffmpeg (required for GIF generation; see scripts\README.md)

OUTPUT:
    - Videos: test-results\videos\
    - GIFs: tests\e2e\fixtures\gifs\

"@
    Write-Host $helpText
    if (-not $Help) {
        exit 1
    }
    exit 0
}

# Check if npm is installed
$npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
if (-not $npmPath) {
    Write-Error-Custom "npm is not installed"
    Write-Host "Install Node.js from https://nodejs.org (version 18+)"
    exit 1
}

Write-Host "=== Playwright Test Recorder ===" -ForegroundColor Blue
Write-Host "Recording test: $TestName"
Write-Host ""

# Build playwright command arguments
$playwrightArgs = @(
    "playwright",
    "test",
    "--config=playwright.config.ts",
    "-g",
    "`"$TestName`""
)

# Add flags
if ($Headed) {
    Write-Info "Mode: Headed (browser visible)"
    $playwrightArgs += "--headed"
} else {
    Write-Info "Mode: Headless"
}

if ($Debug) {
    Write-Info "Debugger: Enabled"
    $playwrightArgs += "--debug"
}

# Ensure video recording directory exists
$videoDir = "test-results\videos"
if (-not (Test-Path -Path $videoDir)) {
    $null = New-Item -ItemType Directory -Path $videoDir -Force
}

# Set environment variable for video recording
$env:PLAYWRIGHT_VIDEO_DIR = $videoDir

Write-Warning-Custom "Running: npx $($playwrightArgs -join ' ')"
Write-Host ""

# Run the test
$playwrightCommand = "npx " + ($playwrightArgs -join " ")
$output = Invoke-Expression $playwrightCommand
$exitCode = $LASTEXITCODE

Write-Host $output

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Success "Test recording completed"
    
    # Find the recorded video
    $videoFiles = @(Get-ChildItem -Path $videoDir -Filter "*.webm" -ErrorAction SilentlyContinue) + 
                  @(Get-ChildItem -Path $videoDir -Filter "*.mp4" -ErrorAction SilentlyContinue)
    
    if ($videoFiles.Count -gt 0) {
        $videoFile = $videoFiles[0].FullName
        $videoSize = "{0:N2} MB" -f ($videoFiles[0].Length / 1MB)
        Write-Host "Video saved: $videoFile ($videoSize)"
        
        # Offer to generate GIF
        if (-not $SkipGif -and -not (Test-Path env:\CI)) {
            Write-Host ""
            $response = Read-Host "Generate demo GIF from this recording? (y/n)"
            if ($response -eq "y" -or $response -eq "Y") {
                # Check for ffmpeg
                $ffmpegPath = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
                if (-not $ffmpegPath) {
                    Write-Error-Custom "ffmpeg is not installed"
                    Write-Host "Install it with:"
                    Write-Host "  Chocolatey: choco install ffmpeg"
                    Write-Host "  Winget: winget install ffmpeg"
                    exit 1
                }
                
                # Create output directory
                $gifDir = "tests\e2e\fixtures\gifs"
                if (-not (Test-Path -Path $gifDir)) {
                    $null = New-Item -ItemType Directory -Path $gifDir -Force
                }
                
                # Default GIF name based on test name
                $gifName = $TestName -replace '[^a-zA-Z0-9]', '-' | ForEach-Object { $_.ToLower() }
                $gifName = $gifName -replace '-demo$', ''
                $gifPath = Join-Path $gifDir "$gifName-demo.gif"
                
                # Prompt for custom name
                $customName = Read-Host "Enter GIF name (or press Enter for default)"
                if (-not [string]::IsNullOrWhiteSpace($customName)) {
                    $gifName = $customName -replace '[^a-zA-Z0-9]', '-' | ForEach-Object { $_.ToLower() }
                    $gifPath = Join-Path $gifDir "$gifName.gif"
                }
                
                Write-Warning-Custom "Generating GIF with $Quality quality..."
                Write-Host ""
                
                # Call gif-from-video.ps1 with selected quality
                $gifScript = ".\scripts\gif-from-video.ps1"
                if (Test-Path -Path $gifScript) {
                    & $gifScript -InputVideo $videoFile -OutputGif $gifPath -Quality $Quality
                    
                    if ($LASTEXITCODE -eq 0) {
                        $gifSize = "{0:N2} MB" -f ((Get-Item $gifPath).Length / 1MB)
                        Write-Success "GIF generated: $gifPath ($gifSize)"
                        
                        # Warn if GIF is large
                        $gifBytes = (Get-Item $gifPath).Length
                        $gifMB = [math]::Round($gifBytes / 1MB, 2)
                        if ($gifMB -gt 3) {
                            Write-Warning-Custom "GIF size is ${gifMB} MB (recommended <3 MB). Consider using -Quality low."
                        }
                    } else {
                        Write-Error-Custom "Failed to generate GIF"
                        exit 1
                    }
                } else {
                    Write-Error-Custom "gif-from-video.ps1 not found: $gifScript"
                    exit 1
                }
            }
        }
    } else {
        Write-Warning-Custom "No video file found in $videoDir"
        Write-Host "Check that your playwright.config.ts has video recording enabled."
    }
} else {
    Write-Host ""
    Write-Error-Custom "Test recording failed (exit code: $exitCode)"
    exit 1
}

Write-Host ""
Write-Success "Done!"
