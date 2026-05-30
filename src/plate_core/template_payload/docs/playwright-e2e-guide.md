# Playwright E2E Testing & Demo GIF Generation Guide

This comprehensive guide covers end-to-end testing with Playwright, recording tests, and generating demo GIFs for documentation.

**Table of Contents:**
1. [Quick Start (5 minutes)](#quick-start-5-minutes)
2. [Running Tests Locally](#running-tests-locally)
3. [Recording Demo GIFs](#recording-demo-gifs)
4. [GIF Quality Guidelines](#gif-quality-guidelines)
5. [CI/CD Integration](#cicd-integration)
6. [Troubleshooting & FAQ](#troubleshooting--faq)
7. [Performance Considerations](#performance-considerations)
8. [Examples: Good vs. Bad GIFs](#examples-good-vs-bad-gifs)

---

## Quick Start (5 minutes)

### 1. Install Prerequisites

Ensure you have:
- **Node.js 18+** — Check with `node --version`
- **npm 9+** — Check with `npm --version`
- **ffmpeg** (for GIF generation) — Optional, but recommended

Install ffmpeg:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
```

### 2. Run Your First Test

```bash
# Install dependencies (if not done yet)
npm install

# Run all E2E tests
npm run test:e2e

# View the HTML report
npx playwright show-report
```

### 3. Record a Demo GIF (5 seconds)

```bash
# Run a specific test and record video
./scripts/e2e-record.sh homepage --headed

# You'll be prompted to generate a GIF
# The script will save it to tests/e2e/fixtures/gifs/homepage-demo.gif
```

**That's it!** Your GIF is ready to embed in documentation.

---

## Running Tests Locally

### Basic Commands

```bash
# Run all tests (headless, parallel)
npm run test:e2e

# Run tests in watch mode (auto-rerun on file changes)
npm run test:e2e:watch

# Run with visible browser (headed mode)
npm run test:e2e:headed

# Run with debugger (Inspector panel)
npm run test:e2e:debug

# Run a specific test file
npx playwright test tests/e2e/specs/example.spec.ts

# Run tests matching a pattern
npx playwright test --grep "login"
```

### Environment Variables

Control test behavior with environment variables:

```bash
# Change base URL (default: http://localhost:3000)
BASE_URL=https://staging.example.com npm run test:e2e

# Run in CI mode (enforces parallelization, retry logic)
CI=true npm run test:e2e

# Enable specific browser (default: chromium; also: firefox, webkit)
npx playwright test --project=firefox
```

### Understanding Test Results

After running tests, results are saved to:

| Location | Purpose | View Command |
|----------|---------|--------------|
| `playwright-report/` | Interactive HTML report | `npx playwright show-report` |
| `test-results/` | Videos (on failure), traces, screenshots | Browse directly |
| `test-results/junit.xml` | Test metadata (count, failures) | `cat` or CI parsing |

**Viewing a recorded video:**
```bash
# Find the video file
ls test-results/**/video.webm

# Convert to GIF for embedding
./scripts/gif-from-video.sh test-results/your-test/video.webm demo.gif
```

---

## Recording Demo GIFs

### Local Recording (Interactive)

Use the `e2e-record.sh` script to record tests and optionally generate GIFs:

```bash
./scripts/e2e-record.sh <test-name> [options]
```

**Examples:**

```bash
# Record a test and optionally generate GIF (medium quality)
./scripts/e2e-record.sh homepage

# Record with visible browser window
./scripts/e2e-record.sh "user login" --headed

# Record with low-quality GIF (smaller file)
./scripts/e2e-record.sh checkout --quality low

# Record and skip the GIF prompt
./scripts/e2e-record.sh "form submission" --skip-gif

# Record with debugger enabled
./scripts/e2e-record.sh payment --debug
```

**Output:**
- Video: `test-results/videos/your-test-name.webm`
- GIF (if generated): `tests/e2e/fixtures/gifs/your-test-name-demo.gif`

### Manual GIF Generation

If you already have a video, convert it to a GIF:

```bash
./scripts/gif-from-video.sh <input-video> <output-gif> [options]
```

**Examples:**

```bash
# Convert with medium quality (recommended for docs)
./scripts/gif-from-video.sh recording.webm demo.gif --quality medium

# Convert with low quality (smallest file, <2 MB)
./scripts/gif-from-video.sh recording.webm demo.gif --quality low

# Convert specific time range (trim to 5 seconds starting at 00:00:02)
./scripts/gif-from-video.sh recording.webm demo.gif --start 00:00:02 --duration 5

# Custom frame rate and width
./scripts/gif-from-video.sh recording.webm demo.gif --fps 20 --width 960
```

### Quality Settings

Choose based on your use case:

| Quality | FPS | Colors | File Size (10s) | Use Case | Command |
|---------|-----|--------|-----------------|----------|---------|
| **Low** | 10 | 64 | ~1.5 MB | Wiki, README, GitHub issues | `--quality low` |
| **Medium** | 15 | 128 | ~3 MB | Feature announcements, key demos | `--quality medium` |
| **High** | 30 | 256 | ~8 MB | ❌ Too large; not recommended | `--quality high` |

**Recommendation:** Use `low` for documentation, `medium` for marketing.

---

## GIF Quality Guidelines

### Target Specifications

For documentation GIFs, aim for:

| Metric | Target | Why |
|--------|--------|-----|
| **File Size** | <3 MB | Fast page load, embedded in GitHub README |
| **Duration** | 3-5 seconds | Shows one complete user action |
| **Frame Rate** | 10-15 fps | Smooth enough for UI interactions, smaller file |
| **Width** | ≥1280px | Readable text, buttons, forms |
| **Clarity** | Text legible, actions clear | Viewers understand the workflow |

### Checklist for Good GIFs

Before committing a GIF, verify:

- [ ] **File size < 3 MB** — Run `ls -lh your-gif.gif`
- [ ] **Duration 3-5 seconds** — Doesn't require ffmpeg analysis
- [ ] **Complete workflow shown** — Someone watching understands the action
- [ ] **Text is legible** — Page content is readable in GIF
- [ ] **Smooth playback** — No stuttering, no blank frames
- [ ] **Meaningful action** — Not just page load, shows an interaction

### Common Issues & Fixes

| Problem | Cause | Solution |
|---------|-------|----------|
| **File > 5 MB** | Quality too high or duration too long | Use `--quality low` or trim with `--duration 5` |
| **Text unreadable** | Width too small or quality too low | Use `--quality medium` or `--width 1280` |
| **Choppy playback** | Frame rate too low | Use `--quality medium` instead of low |
| **Looks pixelated** | Color palette too small | Use `--quality medium` (128 colors) instead of low (64) |

---

## CI/CD Integration

### Automatic GIF Generation in PRs

The CI workflow automatically generates GIFs from test videos **if the PR has the `demo` label**:

1. **Add the `demo` label to your PR**
2. **Tests run and capture videos on failure**
3. **CI converts videos to GIFs automatically** (medium quality)
4. **GIFs are uploaded as artifacts** (90-day retention)
5. **PR comment includes GIF links** and embedding instructions

### Size Validation

The CI workflow validates GIF sizes:

- ⚠️ **Warning**: 3–5 MB (acceptable, but consider trimming)
- ❌ **Fail**: > 5 MB (rejected; must reduce quality or trim)

If GIFs exceed 5 MB:
```bash
# Regenerate locally with low quality
./scripts/gif-from-video.sh test-results/your-test/video.webm demo.gif --quality low

# Commit to repository
git add tests/spike-videos/your-test.gif
git commit -m "test: Add demo GIF for your-test workflow"
```

### Embedding GIFs in Documentation

Once a GIF is committed, embed it in README, CURRENT.md, or wiki:

```markdown
## Demo: User Login Flow

Users can log in with email and password.

**Demo:**
![Login flow demo](tests/e2e/fixtures/gifs/login-demo.gif)

**How it works:**
1. User enters email and password
2. System validates credentials
3. User is redirected to dashboard

**Test:** [specs/login.spec.ts](tests/e2e/specs/login.spec.ts)
**Video (full):** [CI artifacts](https://github.com/...#artifacts)
```

---

## Troubleshooting & FAQ

### Q: Tests fail with "browser not found"

**A:** Install Playwright browsers:
```bash
npx playwright install
```

### Q: Tests fail with "port 3000 already in use"

**A:** Kill the existing process:
```bash
# Find process on port 3000
lsof -i :3000
# Kill by PID
kill <PID>
```

### Q: Tests timeout waiting for development server

**A:** Ensure dev server is running:
```bash
npm run dev &
```

Then run tests:
```bash
npm run test:e2e
```

### Q: GIF generation fails with "ffmpeg not found"

**A:** Install ffmpeg:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
```

### Q: GIF file is too large (> 5 MB)

**A:** Use low quality:
```bash
./scripts/gif-from-video.sh video.webm output.gif --quality low
```

Or trim to essential moments:
```bash
# Capture 5 seconds starting at 2 seconds
./scripts/gif-from-video.sh video.webm output.gif --start 00:00:02 --duration 5 --quality low
```

### Q: How do I debug a failing test?

**A:** Run with the debugger:
```bash
npm run test:e2e:debug

# Or with a specific test
npx playwright test --grep "failing-test-name" --debug
```

The Playwright Inspector opens with:
- Step-through debugging
- Element inspection
- Console access

### Q: How do I run tests on a different environment (staging)?

**A:** Use the `BASE_URL` environment variable:
```bash
BASE_URL=https://staging.example.com npm run test:e2e
```

### Q: Can I run tests in parallel on my machine?

**A:** Yes, control worker count:
```bash
# Single worker (slow, but no parallelization issues)
npx playwright test --workers=1

# Default: 4 workers
npm run test:e2e
```

### Q: How do I record only one test?

**A:** Use the `e2e-record.sh` script with a test name pattern:
```bash
./scripts/e2e-record.sh "homepage loads" --headed
```

### Q: Can I embed GIFs directly in GitHub PRs?

**A:** Yes! Use markdown:
```markdown
![Demo GIF](tests/spike-videos/demo.gif)
```

GitHub will render the GIF inline. Works in PR descriptions, comments, and wiki pages.

---

## Performance Considerations

### Test Execution Performance

| Configuration | Time | Notes |
|---------------|------|-------|
| All tests (4 workers) | ~30-60s | Default, parallelized |
| Single worker | ~2-4 min | Slower, but no race conditions |
| Watch mode (watch ~5 files) | ~10-20s | Only reruns affected tests |
| Headed mode | +50% time | Browser rendering overhead |

**Optimization tips:**
- Use `--workers=4` (default) for fastest CI runs
- Run `--workers=1` for debugging
- Use watch mode during development (`npm run test:e2e:watch`)

### GIF Generation Performance

| Configuration | Time | Notes |
|---------------|------|-------|
| Low quality (10fps) | ~2.3s | Fastest, recommended |
| Medium quality (15fps) | ~3.0s | Balanced |
| High quality (30fps) | ~7.6s | Slow, not recommended |

**Optimization tips:**
- Use `--quality low` for fastest generation
- Trim to 5-10 seconds (avoids palette generation overhead)
- Run on local SSD (not network drive)

### CI/CD Cost Analysis

From GIF generation spike research (`docs/research/gif-generation-spike.md`):

- **GIF generation cost:** < $0.01 per GIF (GitHub Actions @ $0.008/min)
- **Storage cost:** ~$0.02/month per 100 GIFs @ 3MB (GitHub artifacts)
- **Bandwidth cost:** ~$0.01 per 1000 viewers (GitHub Pages free tier)

**Recommendation:** Auto-generate GIFs for `demo`-labeled PRs; safe to enable by default.

---

## Examples: Good vs. Bad GIFs

### ✅ Good GIF Example

**Specifications:**
- File size: 2.1 MB
- Duration: 4 seconds
- Frame rate: 15 fps
- Width: 1280px
- Shows: User login form → submission → success message

**Why it's good:**
- Small enough to embed without slowing page load
- Shows complete action (user understands workflow)
- Text is readable (login form, button labels)
- Smooth playback (no stuttering)
- Perfect for GitHub README or wiki

```markdown
![User Login Demo](tests/e2e/fixtures/gifs/login-demo.gif)
```

### ❌ Bad GIF Examples

**Bad Example 1: File Too Large**
- File size: 8.2 MB
- Duration: 12 seconds
- Frame rate: 30 fps
- Width: 1920px

**Why it's bad:**
- Takes >5 seconds to load over 4G
- Exceeds CI size limit (5 MB)
- Wastes storage and bandwidth
- Not suitable for embedding

**Fix:** Use `--quality low` and trim to 5 seconds:
```bash
./scripts/gif-from-video.sh large-video.webm output.gif --quality low --duration 5
```

**Bad Example 2: Text Unreadable**
- File size: 1.5 MB
- Duration: 8 seconds
- Frame rate: 10 fps
- Width: 640px (too narrow)

**Why it's bad:**
- Text is pixelated and hard to read
- Viewer can't understand form fields
- Defeats the purpose of demo GIF

**Fix:** Use medium quality and wider width:
```bash
./scripts/gif-from-video.sh video.webm output.gif --quality medium --width 1280 --duration 5
```

**Bad Example 3: No Meaningful Action**
- File size: 3.1 MB
- Duration: 3 seconds
- Frame rate: 15 fps
- Content: Just page load, no interaction

**Why it's bad:**
- Doesn't demonstrate workflow
- Viewer doesn't learn anything
- Wastes storage without value

**Fix:** Record test that shows a complete action:
```bash
# Record login workflow, not just page load
./scripts/e2e-record.sh "user can login" --headed
```

### Comparison Table

| Metric | ✅ Good | ❌ Bad |
|--------|---------|---------|
| File size | < 3 MB | > 5 MB |
| Duration | 3-5 sec | > 10 sec or < 1 sec |
| Frame rate | 15-20 fps | 30 fps or 5 fps |
| Width | ≥ 1280px | < 800px |
| Content | Complete action | Page load only |
| Text legibility | Readable | Pixelated |
| Playback | Smooth | Choppy or stuttering |

---

## Further Resources

- **Playwright Docs:** https://playwright.dev/
- **Playwright Best Practices:** https://playwright.dev/docs/best-practices
- **GIF Generation Spike:** [`docs/research/gif-generation-spike.md`](../research/gif-generation-spike.md)
- **E2E Test Setup:** [`tests/e2e/README.md`](../../tests/e2e/README.md)
- **Script Help:** `./scripts/e2e-record.sh --help` and `./scripts/gif-from-video.sh --help`

---

**Last updated:** 2026-05-27  
**Maintainer:** PLATE Template  
**Questions?** See [AGENTS.md](../../AGENTS.md) for support options.
