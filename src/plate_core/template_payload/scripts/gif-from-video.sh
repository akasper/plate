#!/bin/bash

# gif-from-video.sh - Convert Playwright video artifacts to optimized GIFs
# Supports cross-platform usage (Linux/Mac with ffmpeg)
#
# Usage: ./gif-from-video.sh <input_video> <output_gif> [options]
# Options:
#   --quality [high|medium|low]  Output quality (default: medium)
#   --start HH:MM:SS              Start time for trimming (default: 00:00:00)
#   --duration SS                 Duration in seconds (default: entire video)
#   --fps N                        Output frame rate (default: 15)
#   --width N                      Output width in pixels (default: 1280)
#   --help                         Show this help message

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Defaults
QUALITY="medium"
START_TIME="00:00:00"
DURATION=""
OUTPUT_FPS=15
OUTPUT_WIDTH=1280
HELP=0

# Parse arguments
if [[ $# -lt 2 ]]; then
    HELP=1
fi

INPUT_VIDEO="$1"
OUTPUT_GIF="$2"
shift 2

while [[ $# -gt 0 ]]; do
    case $1 in
        --quality)
            QUALITY="$2"
            shift 2
            ;;
        --start)
            START_TIME="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --fps)
            OUTPUT_FPS="$2"
            shift 2
            ;;
        --width)
            OUTPUT_WIDTH="$2"
            shift 2
            ;;
        --help)
            HELP=1
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            HELP=1
            shift
            ;;
    esac
done

if [[ $HELP -eq 1 ]]; then
    cat << 'EOF'
gif-from-video.sh - Convert Playwright video artifacts to optimized GIFs

Usage: ./gif-from-video.sh <input_video> <output_gif> [options]

Arguments:
  input_video    Path to Playwright video file (WebM or MP4)
  output_gif     Path for output GIF file

Options:
  --quality [high|medium|low]  Output quality (default: medium)
                               high:   30fps, full palette, larger file
                               medium: 15fps, optimized palette
                               low:    10fps, reduced palette, smallest file
  --start HH:MM:SS             Start time for trimming (default: 00:00:00)
  --duration SS                Duration in seconds (default: entire video)
  --fps N                       Output frame rate (default: 15)
  --width N                     Output width in pixels (default: 1280)
  --help                        Show this help message

Examples:
  # Convert entire video with medium quality
  ./gif-from-video.sh recording.webm demo.gif

  # Convert with high quality
  ./gif-from-video.sh recording.webm demo.gif --quality high

  # Trim to specific time range
  ./gif-from-video.sh recording.webm demo.gif --start 00:00:05 --duration 10

  # Low quality for smallest file size
  ./gif-from-video.sh recording.webm demo.gif --quality low

EOF
    exit 0
fi

# Validate inputs
if [[ ! -f "$INPUT_VIDEO" ]]; then
    echo -e "${RED}Error: Input video not found: $INPUT_VIDEO${NC}"
    exit 1
fi

# Check for ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}Error: ffmpeg is not installed${NC}"
    echo "Install it with:"
    echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "  Mac: brew install ffmpeg"
    exit 1
fi

# Quality settings
case "$QUALITY" in
    high)
        FPS=30
        COLORS=256
        DITHER="sierra2_4a"
        ;;
    medium)
        FPS=$OUTPUT_FPS
        COLORS=128
        DITHER="sierra2"
        ;;
    low)
        FPS=10
        COLORS=64
        DITHER="bayer:bayer_scale=1"
        ;;
    *)
        echo -e "${RED}Error: Unknown quality: $QUALITY${NC}"
        exit 1
        ;;
esac

# Create temporary directory for palette and frames
TEMP_DIR=$(mktemp -d)
PALETTE_FILE="$TEMP_DIR/palette.png"
FRAMES_DIR="$TEMP_DIR/frames"
mkdir -p "$FRAMES_DIR"

trap "rm -rf $TEMP_DIR" EXIT

echo -e "${YELLOW}Starting GIF generation from: $INPUT_VIDEO${NC}"
echo "Quality: $QUALITY (fps=$FPS, colors=$COLORS, dither=$DITHER)"
echo "Output: $OUTPUT_GIF"

# Build ffmpeg filter chain
FILTER="fps=$FPS,scale=$OUTPUT_WIDTH:-1:flags=lanczos"

# Add trimming if specified
if [[ -n "$DURATION" ]]; then
    TRIM_OPTS="-ss $START_TIME -t $DURATION"
    echo "Trimming: $START_TIME for $DURATION seconds"
else
    TRIM_OPTS="-ss $START_TIME"
    if [[ "$START_TIME" != "00:00:00" ]]; then
        echo "Starting at: $START_TIME"
    fi
fi

# Step 1: Generate palette (optimized for this specific video)
echo -e "${YELLOW}Step 1: Generating color palette...${NC}"
PALETTE_START=$(date +%s%N)
ffmpeg -loglevel error $TRIM_OPTS -i "$INPUT_VIDEO" \
    -vf "$FILTER[x];[x]palettegen=max_colors=$COLORS" \
    "$PALETTE_FILE" 2>&1 | grep -v "^$" || true
PALETTE_END=$(date +%s%N)
PALETTE_TIME=$(( (PALETTE_END - PALETTE_START) / 1000000 ))

# Step 2: Generate GIF using palette
echo -e "${YELLOW}Step 2: Generating GIF...${NC}"
GIF_START=$(date +%s%N)
ffmpeg -loglevel error $TRIM_OPTS -i "$INPUT_VIDEO" \
    -i "$PALETTE_FILE" \
    -lavfi "$FILTER[x];[x][1:v]paletteuse=dither=$DITHER" \
    "$OUTPUT_GIF" 2>&1 | grep -v "^$" || true
GIF_END=$(date +%s%N)
GIF_TIME=$(( (GIF_END - GIF_START) / 1000000 ))

# Calculate file size
INPUT_SIZE=$(stat -f%z "$INPUT_VIDEO" 2>/dev/null || stat -c%s "$INPUT_VIDEO" 2>/dev/null)
OUTPUT_SIZE=$(stat -f%z "$OUTPUT_GIF" 2>/dev/null || stat -c%s "$OUTPUT_GIF" 2>/dev/null)
SIZE_REDUCTION=$(( (INPUT_SIZE - OUTPUT_SIZE) * 100 / INPUT_SIZE ))

echo -e "${GREEN}✓ GIF generation complete!${NC}"
echo ""
echo "Performance Metrics:"
echo "  Palette generation: ${PALETTE_TIME}ms"
echo "  GIF generation:     ${GIF_TIME}ms"
echo "  Total time:         $(( (PALETTE_TIME + GIF_TIME) / 1000 ))s"
echo ""
echo "Size Comparison:"
printf "  Input video:       %6.2f MB\n" $(echo "scale=2; $INPUT_SIZE / 1048576" | bc)
printf "  Output GIF:        %6.2f MB\n" $(echo "scale=2; $OUTPUT_SIZE / 1048576" | bc)
printf "  Reduction:         %6.1f%%\n" "$SIZE_REDUCTION"
echo ""
echo "Output file: $OUTPUT_GIF"
