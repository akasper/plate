#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${1:-.}"
ROOT_DIR="$(cd "$ROOT_DIR" && pwd)"

# .plate platform: absent or empty means posix. Do not infer from the host OS.
# posix-and-windows is matched as a full quoted value so it is not read as posix.
plate_platform="posix"
plate_file="$ROOT_DIR/.plate"
if [[ -f "$plate_file" ]]; then
    pybin=""
    if command -v python3 >/dev/null 2>&1; then
        pybin="python3"
    elif command -v python >/dev/null 2>&1; then
        pybin="python"
    fi
    if [[ -n "$pybin" ]]; then
        if ! plate_platform="$("$pybin" - "$plate_file" <<'PY'
import json, sys
path = sys.argv[1]
allowed = ("posix", "posix-and-windows", "windows")
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except json.JSONDecodeError as exc:
    print(f"invalid JSON in .plate: {exc}", file=sys.stderr)
    sys.exit(2)
if not isinstance(data, dict):
    print(".plate must contain a top-level object", file=sys.stderr)
    sys.exit(2)
value = data.get("platform")
if value is None or value == "":
    value = "posix"
if value not in allowed:
    print(
        f"invalid platform: {value!r} (allowed: posix, posix-and-windows, windows)",
        file=sys.stderr,
    )
    sys.exit(2)
print(value)
PY
)"; then
            exit 1
        fi
        plate_platform="${plate_platform//$'\r'/}"
    elif command -v jq >/dev/null 2>&1; then
        # Real parser. A missing platform key or JSON null still means posix.
        # Trailing commas and other malformed objects are rejected.
        if ! parsed="$(jq -r '
            if type != "object" then
                "error:object"
            elif (.platform | type) == "null" then
                ""
            elif (.platform | type) == "string" then
                .platform
            else
                "error:type"
            end
        ' "$plate_file" 2>/dev/null)"; then
            echo "invalid JSON in .plate: malformed object" >&2
            exit 1
        fi
        parsed="${parsed//$'\r'/}"
        case "$parsed" in
            ""|posix) plate_platform="posix" ;;
            posix-and-windows|windows) plate_platform="$parsed" ;;
            error:object)
                echo ".plate must contain a top-level object" >&2
                exit 1
                ;;
            error:type)
                echo "invalid platform: .plate platform must be a string (allowed: posix, posix-and-windows, windows)" >&2
                exit 1
                ;;
            *)
                echo "invalid platform: $parsed" >&2
                exit 1
                ;;
        esac
    else
        echo "invalid JSON in .plate: cannot parse without python3, python, or jq" >&2
        exit 1
    fi
fi

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

# Check GIF generation scripts for the declared platform.
# Accept scripts/ or scripts/plate/ so namespaced installs still validate.
script_exists() {
    local name="$1"
    [[ -f "$ROOT_DIR/scripts/$name" || -f "$ROOT_DIR/scripts/plate/$name" ]]
}

require_gif() {
    local name="$1"
    if script_exists "$name"; then
        print_check "scripts/$name present" "pass"
    else
        print_check "scripts/$name present" "fail"
    fi
}

echo ""
echo "🎬 GIF Generation Scripts (platform: $plate_platform):"
case "$plate_platform" in
    posix)
        require_gif "gif-from-video.sh"
        ;;
    windows)
        require_gif "gif-from-video.ps1"
        ;;
    posix-and-windows)
        require_gif "gif-from-video.sh"
        require_gif "gif-from-video.ps1"
        ;;
esac

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
