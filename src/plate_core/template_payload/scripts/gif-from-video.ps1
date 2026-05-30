# gif-from-video.ps1 - Convert Playwright video artifacts to optimized GIFs (Windows)
# Supports Windows 10+ with PowerShell 5.1+
#
# Usage: .\gif-from-video.ps1 -InputVideo <path> -OutputGif <path> [options]
# Options:
#   -Quality [high|medium|low]  Output quality (default: medium)
#   -Start <HH:MM:SS>           Start time for trimming (default: 00:00:00)
#   -Duration <seconds>         Duration in seconds (default: entire video)
#   -Fps <number>               Output frame rate (default: 15)
#   -Width <pixels>             Output width in pixels (default: 1280)

param(
    [Parameter(Mandatory=$true, HelpMessage="Input video file path")]
    [string]$InputVideo,
    
    [Parameter(Mandatory=$true, HelpMessage="Output GIF file path")]
    [string]$OutputGif,
    
    [Parameter(HelpMessage="Output quality: high, medium, or low")]
    [ValidateSet("high", "medium", "low")]
    [string]$Quality = "medium",
    
    [Parameter(HelpMessage="Start time in HH:MM:SS format")]
    [string]$Start = "00:00:00",
    
    [Parameter(HelpMessage="Duration in seconds")]
    [int]$Duration = 0,
    
    [Parameter(HelpMessage="Output frame rate")]
    [int]$Fps = 15,
    
    [Parameter(HelpMessage="Output width in pixels")]
    [int]$Width = 1280,
    
    [switch]$Help
)

# Display help
if ($Help) {
    $helpText = @"
gif-from-video.ps1 - Convert Playwright video artifacts to optimized GIFs

USAGE:
    .\gif-from-video.ps1 -InputVideo <path> -OutputGif <path> [options]

PARAMETERS:
    -InputVideo <string>
        Path to Playwright video file (WebM or MP4)
        Required.

    -OutputGif <string>
        Path for output GIF file
        Required.

    -Quality <string>
        Output quality setting
        Options: high, medium, low (default: medium)
        
        high:   30fps, full palette, larger file size
        medium: 15fps, optimized palette
        low:    10fps, reduced palette, smallest file size

    -Start <string>
        Start time for trimming in HH:MM:SS format
        Default: 00:00:00

    -Duration <int>
        Duration in seconds for trimming
        Default: 0 (use entire video)

    -Fps <int>
        Output frame rate (default: 15)

    -Width <int>
        Output width in pixels (default: 1280)

    -Help
        Display this help message

EXAMPLES:
    # Convert entire video with default settings
    .\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif

    # Convert with high quality
    .\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif -Quality high

    # Trim to specific time range
    .\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif `
        -Start 00:00:05 -Duration 10

    # Low quality for smallest file
    .\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif -Quality low

REQUIREMENTS:
    - ffmpeg must be installed and available in PATH
    - Windows 10 or later
    - PowerShell 5.1 or later

INSTALL FFMPEG:
    Using Chocolatey: choco install ffmpeg
    Using Windows Package Manager: winget install ffmpeg
    Manual: https://ffmpeg.org/download.html

"@
    Write-Host $helpText
    exit 0
}

# Color output function
function Write-Success {
    param([string]$Message)
    Write-Host "`u{2713} $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

# Validate inputs
if (-not (Test-Path -Path $InputVideo)) {
    Write-Error-Custom "Input video not found: $InputVideo"
    exit 1
}

# Check for ffmpeg
$ffmpegPath = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ffmpegPath) {
    Write-Error-Custom "ffmpeg is not installed or not in PATH"
    Write-Host "Install it with:"
    Write-Host "  Chocolatey: choco install ffmpeg"
    Write-Host "  Winget: winget install ffmpeg"
    exit 1
}

# Quality settings
switch ($Quality) {
    "high" {
        $outputFps = 30
        $colors = 256
        $dither = "sierra2_4a"
    }
    "medium" {
        $outputFps = $Fps
        $colors = 128
        $dither = "sierra2"
    }
    "low" {
        $outputFps = 10
        $colors = 64
        $dither = "bayer:bayer_scale=1"
    }
}

# Resolve full paths
$InputVideo = (Resolve-Path -Path $InputVideo).Path
$OutputGif = [System.IO.Path]::GetFullPath($OutputGif)

# Create temporary directory
$tempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "gif-gen-$(Get-Random)")
$null = New-Item -ItemType Directory -Path $tempDir -Force
$paletteFile = [System.IO.Path]::Combine($tempDir, "palette.png")

# Cleanup on exit
$cleanupScript = {
    if (Test-Path -Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanupScript -ErrorAction SilentlyContinue

Write-Info "Starting GIF generation..."
Write-Info "Input:   $InputVideo"
Write-Info "Output:  $OutputGif"
Write-Info "Quality: $Quality (fps=$outputFps, colors=$colors, dither=$dither)"

# Build ffmpeg filter
$filter = "fps=$outputFps,scale=$Width\:-1:flags=lanczos"

# Build trim parameters
$trimParams = @()
$trimParams += "-ss"
$trimParams += $Start

if ($Duration -gt 0) {
    $trimParams += "-t"
    $trimParams += $Duration
    Write-Info "Trimming: $Start for $Duration seconds"
} elseif ($Start -ne "00:00:00") {
    Write-Info "Starting at: $Start"
}

# Step 1: Generate palette
Write-Warning-Custom "Step 1: Generating color palette..."
$paletteStopwatch = [System.Diagnostics.Stopwatch]::StartNew()

$paletteArgs = @(
    "-loglevel", "error"
) + $trimParams + @(
    "-i", $InputVideo,
    "-vf", "$filter`[x];[x]palettegen=max_colors=$colors",
    $paletteFile
)

& ffmpeg $paletteArgs 2>&1 | Where-Object { $_ -match '\S' } | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to generate palette (exit code: $LASTEXITCODE)"
    & $cleanupScript
    exit 1
}

$paletteStopwatch.Stop()
$paletteMs = $paletteStopwatch.ElapsedMilliseconds

# Step 2: Generate GIF
Write-Warning-Custom "Step 2: Generating GIF..."
$gifStopwatch = [System.Diagnostics.Stopwatch]::StartNew()

$gifArgs = @(
    "-loglevel", "error"
) + $trimParams + @(
    "-i", $InputVideo,
    "-i", $paletteFile,
    "-lavfi", "$filter`[x];[x][1:v]paletteuse=dither=$dither",
    $OutputGif
)

& ffmpeg $gifArgs 2>&1 | Where-Object { $_ -match '\S' } | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to generate GIF (exit code: $LASTEXITCODE)"
    & $cleanupScript
    exit 1
}

$gifStopwatch.Stop()
$gifMs = $gifStopwatch.ElapsedMilliseconds

# Get file sizes
$inputSize = (Get-Item -Path $InputVideo).Length
$outputSize = (Get-Item -Path $OutputGif).Length
$sizeReduction = [math]::Round(($inputSize - $outputSize) * 100 / $inputSize)

Write-Success "GIF generation complete!"
Write-Host ""
Write-Host "Performance Metrics:" -ForegroundColor Cyan
Write-Host "  Palette generation: ${paletteMs}ms"
Write-Host "  GIF generation:     ${gifMs}ms"
Write-Host "  Total time:         $([math]::Round(($paletteMs + $gifMs) / 1000, 1))s"
Write-Host ""
Write-Host "Size Comparison:" -ForegroundColor Cyan
Write-Host "  Input video:  $('{0:N2}' -f ($inputSize / 1MB)) MB"
Write-Host "  Output GIF:   $('{0:N2}' -f ($outputSize / 1MB)) MB"
Write-Host "  Reduction:    ${sizeReduction}%"
Write-Host ""
Write-Host "Output file: $OutputGif" -ForegroundColor Green

# Cleanup
& $cleanupScript
