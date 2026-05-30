# E2E Test Demo GIFs

This directory contains animated GIF files generated from E2E test recordings. These GIFs demonstrate key user workflows and are suitable for embedding in documentation, READMEs, and GitHub wiki pages.

## Directory Contents

### `homepage-demo.gif`

**Specifications:**
- File size: 3.52 MB
- Duration: 10 seconds
- Frame rate: 10 fps
- Width: 1280px
- Quality: Low (64 colors)
- Source: Test spike video (`tests/spike-videos/test-low.gif`)

**Use case:** Example demo GIF for documentation and wiki embedding.

**Markdown embedding:**
```markdown
![Homepage Demo](tests/e2e/fixtures/gifs/homepage-demo.gif)
```

## Adding New GIFs

### Method 1: CI Auto-Generation (Recommended for PRs)

1. Add the `demo` label to your PR
2. Push a commit with failing E2E tests
3. CI automatically generates GIFs from test videos
4. Download GIFs from CI artifacts and commit them:

```bash
# Download from GitHub Actions artifacts
git add tests/e2e/fixtures/gifs/*.gif
git commit -m "test: Add demo GIFs from E2E test run"
```

### Method 2: Local Recording

Record a test locally and generate a GIF:

```bash
# Record a test and generate GIF interactively
./scripts/e2e-record.sh "homepage loads" --headed

# When prompted, choose to generate GIF
# GIF will be saved to tests/e2e/fixtures/gifs/homepage-loads-demo.gif
```

### Method 3: Manual GIF Generation

If you already have a video, convert it to a GIF:

```bash
# Convert with low quality (recommended for docs, <3 MB)
./scripts/gif-from-video.sh test-results/test-name/video.webm homepage-demo.gif --quality low

# Or medium quality for better visual fidelity (~3 MB)
./scripts/gif-from-video.sh test-results/test-name/video.webm homepage-demo.gif --quality medium

# Trim to specific time range for smaller files
./scripts/gif-from-video.sh test-results/test-name/video.webm homepage-demo.gif \
  --quality low --start 00:00:02 --duration 5
```

## File Size Guidelines

| Quality | File Size (typical) | Use Case | Recommended |
|---------|------------------|----------|-------------|
| Low | 1–2 MB | Wiki, README, GitHub issues | ✅ Yes |
| Medium | 2–4 MB | Feature announcements | ✅ Yes |
| High | 6–8 MB | ❌ Too large for web | No |

**Best practice:** Keep GIFs under 3 MB for fast page loads.

## Naming Conventions

Use kebab-case (lowercase with hyphens) for GIF filenames:

```
✅ homepage-demo.gif
✅ user-login-flow.gif
✅ form-validation-error.gif

❌ homepageDemo.gif
❌ userLoginFlow.gif
❌ form validation error.gif
```

## Embedding in Documentation

### In README.md

```markdown
## User Login Flow

Users can log in with email and password.

**Demo:**
![Login flow](tests/e2e/fixtures/gifs/user-login-flow.gif)

**Test:** [tests/e2e/specs/login.spec.ts](../specs/login.spec.ts)
```

### In Wiki Pages

Create a wiki page with embedded GIFs:

```markdown
# Feature Demonstrations

## Homepage Loading

![Homepage loads](../../tests/e2e/fixtures/gifs/homepage-demo.gif)

The homepage loads quickly and displays all key UI elements.
```

### In CURRENT.md

```markdown
| Demo GIF Generation | CI + Local | Automatic on 'demo' PR label | Generated from E2E tests | `tests/e2e/fixtures/gifs/` |
```

## Verification Checklist

Before committing a new GIF, verify:

- [ ] File size < 3 MB (check with `ls -lh`)
- [ ] Duration 3–5 seconds (shows one complete user action)
- [ ] Frame rate 10–15 fps (smooth but efficient)
- [ ] Width ≥ 1280px (readable text and buttons)
- [ ] Text is legible (buttons, form labels, messages visible)
- [ ] Shows a meaningful action (not just page load)
- [ ] Smooth playback (no stuttering or blank frames)

## Troubleshooting

**GIF file is too large (> 5 MB)**
```bash
# Regenerate with low quality
./scripts/gif-from-video.sh video.webm output.gif --quality low

# Or trim to essential moments
./scripts/gif-from-video.sh video.webm output.gif --duration 5 --quality low
```

**Text is unreadable in GIF**
```bash
# Use medium quality (128 colors instead of 64)
./scripts/gif-from-video.sh video.webm output.gif --quality medium
```

**GIF playback is choppy**
```bash
# Increase frame rate
./scripts/gif-from-video.sh video.webm output.gif --quality medium --fps 15
```

For more help, see:
- [`docs/playwright-e2e-guide.md`](../../../docs/playwright-e2e-guide.md) — Comprehensive GIF guide
- [`scripts/gif-from-video.sh --help`](../../../scripts/gif-from-video.sh) — Script help
- [`tests/e2e/README.md`](../README.md) — E2E testing guide

---

**Last updated:** 2026-05-27
