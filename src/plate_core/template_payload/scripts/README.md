# Recording and GIF Generation Scripts

This directory contains scripts for recording Playwright E2E test videos and converting them to optimized GIFs for documentation and wiki articles.

## Quick Start

### macOS/Linux

```bash
# Record a test
./scripts/e2e-record.sh login

# Record with visible browser
./scripts/e2e-record.sh login --headed

# Record and generate a low-quality GIF
./scripts/e2e-record.sh homepage --quality low
```

### Windows (PowerShell)

```powershell
# Record a test
.\scripts\e2e-record.ps1 -TestName "login"

# Record with visible browser
.\scripts\e2e-record.ps1 -TestName "login" -Headed

# Record and generate a low-quality GIF
.\scripts\e2e-record.ps1 -TestName "homepage" -Quality low
```

## Installation Requirements

### Node.js
- Version 18 or higher
- Install from [nodejs.org](https://nodejs.org)
- Verify: `node --version` and `npm --version`

### Playwright
- Installed via npm in your project
- Videos are automatically captured by Playwright if enabled in `playwright.config.ts`
- Required config:
  ```typescript
  use: {
    video: 'on', // or 'retain-on-failure'
  }
  ```

### ffmpeg (for GIF generation)

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

**Windows (Chocolatey):**
```powershell
choco install ffmpeg
```

**Windows (Winget):**
```powershell
winget install ffmpeg
```

**Manual installation:**
- Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- Ensure `ffmpeg` is in your system PATH

**Verify installation:**
```bash
ffmpeg -version
```

## Recording Scripts

### e2e-record.sh (macOS/Linux)

Records a single Playwright test and optionally generates a GIF.

**Usage:**
```bash
./scripts/e2e-record.sh <test-name> [options]
```

**Options:**
- `--headed` - Run with visible browser (default: headless)
- `--debug` - Enable Playwright Inspector
- `--quality {high|medium|low}` - GIF quality if generating (default: medium)
- `--skip-gif` - Don't offer to generate GIF
- `--help` - Show help

**Examples:**
```bash
# Record test "should login" in headless mode
./scripts/e2e-record.sh "should login"

# Record with visible browser
./scripts/e2e-record.sh login --headed

# Record with debugger
./scripts/e2e-record.sh checkout --debug

# Skip GIF generation
./scripts/e2e-record.sh homepage --skip-gif
```

**Output:**
- Video: `test-results/videos/<test-name>-<timestamp>.webm`
- GIF (optional): `tests/e2e/fixtures/gifs/<test-name>-demo.gif`

### e2e-record.ps1 (Windows)

PowerShell equivalent of the bash script. Same functionality and options.

**Usage:**
```powershell
.\scripts\e2e-record.ps1 -TestName <name> [options]
```

**Options:**
- `-Headed` - Run with visible browser
- `-Debug` - Enable Playwright Inspector
- `-Quality <high|medium|low>` - GIF quality (default: medium)
- `-SkipGif` - Don't offer to generate GIF
- `-Help` - Show help

**Examples:**
```powershell
# Record test
.\scripts\e2e-record.ps1 -TestName "login"

# Record with visible browser
.\scripts\e2e-record.ps1 -TestName "login" -Headed

# Skip GIF generation
.\scripts\e2e-record.ps1 -TestName "homepage" -SkipGif
```

**Output:**
- Same as bash version (paths use Windows separators)

## GIF Generation Scripts

### gif-from-video.sh (macOS/Linux)

Converts video files to optimized GIFs using ffmpeg and palette optimization.

**Usage:**
```bash
./scripts/gif-from-video.sh <input_video> <output_gif> [options]
```

**Options:**
- `--quality {high|medium|low}` - Quality level (default: medium)
- `--start HH:MM:SS` - Start time for trimming (default: 00:00:00)
- `--duration SS` - Duration in seconds (default: entire video)
- `--fps N` - Output frame rate (default: 15)
- `--width N` - Output width in pixels (default: 1280)
- `--help` - Show help

**Quality Settings:**

| Quality | FPS | Colors | Dithering | Typical Size | Use Case |
|---------|-----|--------|-----------|--------------|----------|
| high    | 30  | 256    | sierra2_4a | 12-16 MB | Premium documentation, short clips |
| medium  | 15  | 128    | sierra2    | 3-6 MB | Default, balanced quality |
| low     | 10  | 64     | bayer     | 1-3 MB | Web docs, bandwidth-limited |

**Examples:**
```bash
# Convert entire video with default settings
./scripts/gif-from-video.sh recording.webm demo.gif

# Convert with high quality
./scripts/gif-from-video.sh recording.webm demo.gif --quality high

# Trim to specific time range (5 seconds starting at 2 seconds)
./scripts/gif-from-video.sh recording.webm demo.gif --start 00:00:02 --duration 5

# Generate low-quality GIF for web
./scripts/gif-from-video.sh recording.webm demo.gif --quality low --width 800
```

### gif-from-video.ps1 (Windows)

PowerShell equivalent with identical functionality.

**Usage:**
```powershell
.\scripts\gif-from-video.ps1 -InputVideo <path> -OutputGif <path> [options]
```

**Options:**
- `-Quality <high|medium|low>` - Quality level (default: medium)
- `-Start <HH:MM:SS>` - Start time for trimming
- `-Duration <seconds>` - Duration in seconds
- `-Fps <number>` - Output frame rate (default: 15)
- `-Width <pixels>` - Output width in pixels (default: 1280)
- `-Help` - Show help

**Examples:**
```powershell
# Convert entire video
.\scripts\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif

# Convert with high quality
.\scripts\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif -Quality high

# Trim and convert
.\scripts\gif-from-video.ps1 -InputVideo recording.webm -OutputGif demo.gif `
    -Start 00:00:02 -Duration 5
```

## Workflow: Recording and Publishing Demo GIFs

### Step 1: Run the Recording Script

Choose headless or headed mode:

```bash
# Headless (recommended for CI-like environments)
./scripts/e2e-record.sh "feature name"

# Headed (interact with the browser manually)
./scripts/e2e-record.sh "feature name" --headed
```

The script will:
1. Run the Playwright test
2. Record video to `test-results/videos/`
3. Offer to generate a GIF

### Step 2: Accept GIF Generation

When prompted, enter `y` to generate a GIF. Choose quality level:
- **low**: Smallest file, good for web docs (typical: 1-3 MB)
- **medium**: Balanced (typical: 3-6 MB) — recommended default
- **high**: Best quality for premium docs (typical: 12-16 MB)

### Step 3: Name the GIF

The script suggests a name based on the test. You can:
- Press Enter to accept the default
- Enter a custom name (spaces and special chars are converted to hyphens)

### Step 4: Verify Output

The script prints the GIF path:
```
✓ GIF generated: tests/e2e/fixtures/gifs/login-demo.gif (2.8 MB)
```

### Step 5: Commit and Document

```bash
# Add to git
git add tests/e2e/fixtures/gifs/login-demo.gif

# Commit
git commit -m "Add login demo GIF"

# Include in PR description or wiki
![Login Demo](../../fixtures/gifs/login-demo.gif)
```

## Troubleshooting

### "npm is not installed"

**Solution:** Install Node.js from [nodejs.org](https://nodejs.org). Verify with:
```bash
node --version  # Should be 18+
npm --version
```

### "ffmpeg is not installed"

**Solution:** See [Installation Requirements](#ffmpeg-for-gif-generation) section above.

### "Test not found"

The test pattern didn't match. Check available tests:

```bash
# Run with verbose output
npx playwright test --list

# Try a broader pattern
./scripts/e2e-record.sh "login"  # Matches any test with "login" in the name
```

### "No video file found"

Check that `playwright.config.ts` has video recording enabled:

```typescript
use: {
  video: 'on',  // or 'retain-on-failure'
}
```

Also verify that:
1. `test-results/` directory exists and is writable
2. The test actually ran (check console output)
3. The test duration was >100ms (very fast tests may not record)

### "GIF file size exceeds 5 MB"

Use lower quality settings:

```bash
# Low quality: typically 1-3 MB
./scripts/e2e-record.sh homepage --quality low

# Or trim the video
./scripts/gif-from-video.sh recording.webm demo.gif \
    --quality medium \
    --start 00:00:02 \
    --duration 5
```

### "GIF looks blocky or pixelated"

Try higher quality:

```bash
./scripts/e2e-record.sh homepage --quality high
```

Note: High quality produces larger files (12-16 MB).

### CI Environment

In CI (GitHub Actions, Jenkins, etc.), set the `CI` environment variable to skip interactive prompts:

```yaml
- name: Record test
  env:
    CI: true
  run: ./scripts/e2e-record.sh login --quality low --skip-gif
```

## Performance Expectations

### Recording Time
- Typically 1-3 seconds faster than the actual test duration
- Headed mode adds browser startup time (~2-3 seconds)
- Debug mode adds inspector startup time (~5 seconds)

### GIF Generation Time
- **Low quality**: 3-5 seconds
- **Medium quality**: 5-8 seconds
- **High quality**: 8-15 seconds
- Time scales with video duration

### File Sizes (10-second test video)

| Quality | Settings | Typical Size |
|---------|----------|--------------|
| Low | 10fps, 64 colors | 1-2 MB |
| Medium | 15fps, 128 colors | 3-5 MB |
| High | 30fps, 256 colors | 12-16 MB |

Smaller videos produce proportionally smaller GIFs.

## Integration with Package.json

Add npm scripts for easy access:

```json
{
  "scripts": {
    "record": "chmod +x scripts/e2e-record.sh && ./scripts/e2e-record.sh",
    "record:headed": "chmod +x scripts/e2e-record.sh && ./scripts/e2e-record.sh --headed",
    "gif:convert": "chmod +x scripts/gif-from-video.sh && ./scripts/gif-from-video.sh"
  }
}
```

Then run:
```bash
npm run record -- login          # Record login test
npm run record:headed -- login   # Record with visible browser
npm run gif:convert -- video.webm demo.gif  # Convert video to GIF
```

## Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `PLAYWRIGHT_HEADED` | Force headed mode | `export PLAYWRIGHT_HEADED=1` |
| `PLAYWRIGHT_DEBUG` | Enable debug mode | `export PLAYWRIGHT_DEBUG=1` |
| `PLAYWRIGHT_VIDEO_DIR` | Custom video output directory | `export PLAYWRIGHT_VIDEO_DIR=./my-videos` |
| `CI` | Skip interactive prompts | `export CI=true` |

## Advanced: Standalone GIF Conversion

Use the GIF scripts independently to convert any video:

```bash
# Convert MP4 to GIF
./scripts/gif-from-video.sh movie.mp4 demo.gif --quality medium

# Extract and convert specific time range
./scripts/gif-from-video.sh recording.webm excerpt.gif \
    --start 00:00:10 \
    --duration 5 \
    --quality low

# Custom dimensions
./scripts/gif-from-video.sh recording.webm demo.gif \
    --width 800 \
    --fps 12 \
    --quality low
```

## See Also

- [GIF Generation Spike Report](../docs/research/gif-generation-spike.md) - Technical details on quality settings and performance
- [Playwright Documentation](https://playwright.dev) - Full Playwright API reference
- [FFmpeg Filters](https://ffmpeg.org/ffmpeg-filters.html) - FFmpeg documentation
