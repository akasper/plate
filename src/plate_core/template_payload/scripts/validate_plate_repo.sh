#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${1:-.}"
ROOT_DIR="$(cd "$ROOT_DIR" && pwd)"

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track validation failures
VALIDATION_ERRORS=0

# Helper function to print pass/fail messages
print_check() {
    local message="$1"
    local status="$2"
    
    if [[ "$status" == "pass" ]]; then
        echo -e "${GREEN}✓${NC} $message"
    elif [[ "$status" == "fail" ]]; then
        echo -e "${RED}✗${NC} $message"
        VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
    elif [[ "$status" == "warn" ]]; then
        echo -e "${YELLOW}⚠${NC} $message"
    fi
}

echo "=== PLATE Repository Validation ==="
echo ""

# === Core PLATE Artifacts ===
echo "📋 Core PLATE Artifacts:"
required_files=(
    "AGENTS.md"
    "CURRENT.md"
    "SPEC.md"
    ".agentic/process.yml"
    ".agentic/skills.yml"
    ".github/copilot-instructions.md"
    ".github/workflows/ci.yml"
)

for rel in "${required_files[@]}"; do
    if [[ -f "$ROOT_DIR/$rel" ]]; then
        print_check "$rel" "pass"
    else
        print_check "$rel" "fail"
    fi
done

echo ""
echo "🎭 Playwright E2E Setup:"

# Check playwright.config.ts
if [[ -f "$ROOT_DIR/playwright.config.ts" ]]; then
    print_check "playwright.config.ts present" "pass"
else
    print_check "playwright.config.ts present" "fail"
fi

# Check E2E directory structure
e2e_dir="$ROOT_DIR/tests/e2e"
if [[ -d "$e2e_dir" ]]; then
    print_check "tests/e2e/ directory exists" "pass"
    
    # Check required subdirectories
    for subdir in pages specs fixtures; do
        if [[ -d "$e2e_dir/$subdir" ]]; then
            print_check "  └─ $subdir/" "pass"
        else
            print_check "  └─ $subdir/" "fail"
        fi
    done
else
    print_check "tests/e2e/ directory exists" "fail"
fi

# Check for test specs
if [[ -d "$e2e_dir/specs" ]]; then
    spec_count=$(find "$e2e_dir/specs" -name "*.spec.ts" -o -name "*.spec.js" | wc -l)
    if [[ $spec_count -gt 0 ]]; then
        print_check "Test specs present ($spec_count found)" "pass"
    else
        print_check "Test specs present" "fail"
    fi
fi

# Check npm scripts for E2E commands
echo ""
echo "📦 npm Scripts:"
package_json="$ROOT_DIR/package.json"

if [[ -f "$package_json" ]]; then
    if grep -q '"test:e2e"' "$package_json"; then
        print_check "test:e2e script defined" "pass"
    else
        print_check "test:e2e script defined" "fail"
    fi
    
    if grep -q '"record:e2e"' "$package_json"; then
        print_check "record:e2e script defined" "pass"
    else
        print_check "record:e2e script defined" "fail"
    fi
else
    print_check "package.json found" "fail"
fi

# Check GIF generation scripts
echo ""
echo "🎬 GIF Generation Scripts:"
if [[ -f "$ROOT_DIR/scripts/gif-from-video.sh" ]]; then
    print_check "scripts/gif-from-video.sh present" "pass"
else
    print_check "scripts/gif-from-video.sh present" "fail"
fi

if [[ -f "$ROOT_DIR/scripts/gif-from-video.ps1" ]]; then
    print_check "scripts/gif-from-video.ps1 present" "pass"
else
    print_check "scripts/gif-from-video.ps1 present" "fail"
fi

# Check CI workflow
echo ""
echo "⚙️  CI Configuration:"
if [[ -f "$ROOT_DIR/.github/workflows/test-e2e.yml" ]]; then
    print_check ".github/workflows/test-e2e.yml present" "pass"
else
    print_check ".github/workflows/test-e2e.yml present" "fail"
fi

# === Runtime Validation ===
echo ""
echo "🔧 Runtime Configuration:"
ci_file="$ROOT_DIR/.github/workflows/ci.yml"
copilot_file="$ROOT_DIR/.github/copilot-instructions.md"
current_file="$ROOT_DIR/CURRENT.md"

has_runtime=false
for manifest in package.json pyproject.toml requirements.txt wally.toml default.project.json rojo.json; do
    if [[ -f "$ROOT_DIR/$manifest" ]]; then
        has_runtime=true
        break
    fi
done

if $has_runtime; then
    if grep -q 'echo "Tests would run here"' "$ci_file"; then
        print_check "CI uses placeholder test command" "fail"
    else
        print_check "CI configured for real tests" "pass"
    fi

    if grep -qi 'does not define a local build, lint, or test toolchain yet' "$copilot_file"; then
        print_check "Copilot instructions claim no toolchain" "fail"
    else
        print_check "Copilot instructions updated for toolchain" "pass"
    fi

    if grep -qi 'Project-specific CI commands are not defined by the generic template' "$current_file"; then
        print_check "CURRENT.md says CI not configured" "fail"
    else
        print_check "CURRENT.md reflects real CI config" "pass"
    fi
fi

echo ""
echo "=== Validation Summary ==="
if [[ $VALIDATION_ERRORS -eq 0 ]]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ $VALIDATION_ERRORS check(s) failed${NC}"
    exit 1
fi
