# Playwright Video to GIF Generation

- **Issue:** #135
- **Researched by:** Copilot / PLATE automation
- **Date:** 2026-05-27
- **Status:** Completed

## Research Question

What is the minimal, reliable, cross-platform way to turn Playwright-generated video clips into small, embeddable GIFs for durable "in action" demos?

## Sources

- `docs/research/gif-generation-spike.md`
- `tests/spike-videos/TEST_RESULTS.md`
- `scripts/gif-from-video.sh`
- `scripts/gif-from-video.ps1`

## Findings

FFmpeg with palette optimization is the best default because it is:

- cross-platform
- deterministic
- offline
- fast enough for CI and local use
- easy to script from Bash and PowerShell

### Recommended encoder strategy

1. Trim to the important moment first.
2. Generate a palette.
3. Encode with `paletteuse`.
4. Prefer lower frame rates and fewer colors for documentation use.

### Quality guidance

| Quality | Use case | Typical result |
|---|---|---|
| Low | Docs, PRs, wiki embeds | Smallest files, best default |
| Medium | Feature announcements | Better readability, still manageable |
| High | Archives only | Usually too large for committed evidence |

### Benchmarks

From the spike results:

- 10s clip, low quality: `3.52 MB`
- 5s clip, medium quality: `3.19 MB`
- 5s clip, low quality: `1.81 MB`

That makes low-quality GIFs the safest default for durable PR evidence.

### Cross-platform notes

- Bash script: `scripts/gif-from-video.sh`
- PowerShell script: `scripts/gif-from-video.ps1`
- Both should check for `ffmpeg` and fail clearly when it is missing

## Recommendation

Use FFmpeg palette optimization as the default implementation, and keep the scripts in sync across Bash and PowerShell so local recording and CI post-processing behave the same way.

The spike report in `docs/research/gif-generation-spike.md` remains the detailed benchmark record; this file is the issue-specific research artifact for #135.
