#!/bin/bash

# e2e-record.sh - Record Playwright E2E tests locally with optional demo GIF generation
# Supports Linux and macOS
#
# Usage: ./scripts/e2e-record.sh [test-name] [--headed] [--debug] [--quality {high|medium|low}]
# 
# Arguments:
#   test-name           Name or pattern of the test to record (matches Playwright test name)
#   --headed            Run test in headed mode (visible browser)
#   --debug             Enable Playwright Inspector for debugging
#   --quality {level}   GIF quality if generating GIF: high, medium, or low (default: medium)
#   --skip-gif          Don't offer to generate GIF (just record video)
#   --help              Show this help message

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
TEST_NAME=""
HEADED=false
DEBUG=false
GIF_QUALITY="medium"
SKIP_GIF=false
HELP=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --headed)
            HEADED=true
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --quality)
            GIF_QUALITY="$2"
            shift 2
            ;;
        --skip-gif)
            SKIP_GIF=true
            shift
            ;;
        --help)
            HELP=1
            shift
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            HELP=1
            shift
            ;;
        *)
            if [[ -z "$TEST_NAME" ]]; then
                TEST_NAME="$1"
            fi
            shift
            ;;
    esac
done

if [[ $HELP -eq 1 ]] || [[ -z "$TEST_NAME" ]]; then
    cat << 'EOF'
e2e-record.sh - Record Playwright E2E tests with optional GIF generation

Usage: ./scripts/e2e-record.sh <test-name> [options]

Arguments:
  test-name          Name or pattern of the test to record
                    (matches Playwright test name)

Options:
  --headed          Run test in headed mode (visible browser window)
  --debug           Enable Playwright Inspector for debugging
  --quality LEVEL   GIF quality if generating GIF: high, medium, or low
                    (default: medium)
  --skip-gif        Don't offer to generate GIF (just record video)
  --help            Show this help message

Examples:
  # Record a test in headless mode
  ./scripts/e2e-record.sh login

  # Record with visible browser (headed mode)
  ./scripts/e2e-record.sh "user creation" --headed

  # Record with debugger
  ./scripts/e2e-record.sh checkout --debug

  # Record and generate low-quality GIF
  ./scripts/e2e-record.sh homepage --quality low

Environment Variables:
  PLAYWRIGHT_HEADED    Set to 1 for headed mode (can be overridden by --headed flag)
  PLAYWRIGHT_DEBUG     Set to 1 for debug mode
  CI                   If set, assumes CI environment and skips interactive prompts

Dependencies:
  - Node.js 18+
  - npm or yarn
  - Playwright (installed via npm)
  - ffmpeg (required for GIF generation; see scripts/README.md)

Output:
  - Videos are saved to: test-results/videos/
  - GIFs can be saved to: tests/e2e/fixtures/gifs/

EOF
    exit 0
fi

# Check if Node.js and npm are available
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed${NC}"
    echo "Install Node.js from https://nodejs.org (version 18+)"
    exit 1
fi

echo -e "${BLUE}=== Playwright Test Recorder ===${NC}"
echo "Recording test: $TEST_NAME"

# Build playwright command
PW_OPTS="--config=playwright.config.ts"
PW_OPTS="$PW_OPTS -g \"$TEST_NAME\""

if [[ "$HEADED" == "true" ]]; then
    echo -e "${YELLOW}Mode: Headed (browser visible)${NC}"
    PW_OPTS="$PW_OPTS --headed"
else
    echo -e "${YELLOW}Mode: Headless${NC}"
fi

if [[ "$DEBUG" == "true" ]]; then
    echo -e "${YELLOW}Debugger: Enabled${NC}"
    PW_OPTS="$PW_OPTS --debug"
fi

# Ensure video recording is enabled
export PLAYWRIGHT_VIDEO_DIR="test-results/videos"
mkdir -p "$PLAYWRIGHT_VIDEO_DIR"

echo -e "${YELLOW}Running: npx playwright test $PW_OPTS${NC}"
echo ""

# Run the test with video recording
if eval "npx playwright test $PW_OPTS"; then
    echo ""
    echo -e "${GREEN}✓ Test recording completed${NC}"
    
    # Find the recorded video
    VIDEO_FILE=$(find "$PLAYWRIGHT_VIDEO_DIR" -name "*.webm" -o -name "*.mp4" | head -1)
    
    if [[ -n "$VIDEO_FILE" ]]; then
        VIDEO_SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
        echo "Video saved: $VIDEO_FILE ($VIDEO_SIZE)"
        
        # Offer to generate GIF
        if [[ "$SKIP_GIF" != "true" ]] && [[ -z "$CI" ]]; then
            echo ""
            read -p "Generate demo GIF from this recording? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                # Check for ffmpeg
                if ! command -v ffmpeg &> /dev/null; then
                    echo -e "${RED}Error: ffmpeg is not installed${NC}"
                    echo "Install it with:"
                    echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
                    echo "  Mac: brew install ffmpeg"
                    exit 1
                fi
                
                # Create output directory
                GIF_DIR="tests/e2e/fixtures/gifs"
                mkdir -p "$GIF_DIR"
                
                # Default GIF name based on test name
                GIF_NAME=$(echo "$TEST_NAME" | sed 's/[^a-zA-Z0-9]/-/g' | tr '[:upper:]' '[:lower:]' | sed 's/-demo$//')
                GIF_PATH="$GIF_DIR/${GIF_NAME}-demo.gif"
                
                # Prompt for custom name
                read -p "Enter GIF name (or press Enter for default): " CUSTOM_NAME
                if [[ -n "$CUSTOM_NAME" ]]; then
                    GIF_NAME=$(echo "$CUSTOM_NAME" | sed 's/[^a-zA-Z0-9]/-/g' | tr '[:upper:]' '[:lower:]')
                    GIF_PATH="$GIF_DIR/${GIF_NAME}.gif"
                fi
                
                echo -e "${YELLOW}Generating GIF with $GIF_QUALITY quality...${NC}"
                
                # Call gif-from-video.sh with selected quality
                if [[ -x "./scripts/gif-from-video.sh" ]]; then
                    if ./scripts/gif-from-video.sh "$VIDEO_FILE" "$GIF_PATH" --quality "$GIF_QUALITY"; then
                        GIF_SIZE=$(du -h "$GIF_PATH" | cut -f1)
                        echo -e "${GREEN}✓ GIF generated: $GIF_PATH ($GIF_SIZE)${NC}"
                        
                        # Warn if GIF is large
                        GIF_BYTES=$(stat -f%z "$GIF_PATH" 2>/dev/null || stat -c%s "$GIF_PATH" 2>/dev/null)
                        GIF_MB=$(echo "scale=2; $GIF_BYTES / 1048576" | bc)
                        if (( $(echo "$GIF_MB > 3" | bc -l) )); then
                            echo -e "${YELLOW}⚠ GIF size is ${GIF_MB} MB (recommended <3 MB). Consider using --quality low.${NC}"
                        fi
                    else
                        echo -e "${RED}Error: Failed to generate GIF${NC}"
                        exit 1
                    fi
                else
                    echo -e "${RED}Error: gif-from-video.sh not found or not executable${NC}"
                    echo "Make it executable: chmod +x scripts/gif-from-video.sh"
                    exit 1
                fi
            fi
        fi
    else
        echo -e "${YELLOW}Note: No video file found in $PLAYWRIGHT_VIDEO_DIR${NC}"
        echo "Check that your playwright.config.ts has video recording enabled."
    fi
else
    echo -e "${RED}✗ Test recording failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Done!${NC}"
