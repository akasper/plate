#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${1:-.}"
ROOT_DIR="$(cd "$ROOT_DIR" && pwd)"

missing=()

need_tool() {
    local cmd="$1"
    local reason="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd|$reason")
    fi
}

need_tool "gh" "required for repository bootstrap and GitHub automation"
need_tool "git" "required for repository bootstrap and wiki initialization"

if [[ -f "$ROOT_DIR/package.json" ]]; then
    need_tool "node" "required because package.json is present"
    need_tool "npm" "required because package.json is present"
fi

if [[ -f "$ROOT_DIR/pnpm-lock.yaml" ]]; then
    need_tool "node" "required because pnpm-lock.yaml is present"
    need_tool "pnpm" "required because pnpm-lock.yaml is present"
fi

if [[ -f "$ROOT_DIR/yarn.lock" ]]; then
    need_tool "node" "required because yarn.lock is present"
    need_tool "yarn" "required because yarn.lock is present"
fi

if [[ -f "$ROOT_DIR/wally.toml" ]]; then
    need_tool "wally" "required because wally.toml is present"
fi

if [[ -f "$ROOT_DIR/default.project.json" || -f "$ROOT_DIR/rojo.json" ]]; then
    need_tool "rojo" "required because Rojo project metadata is present"
fi

if (( ${#missing[@]} > 0 )); then
    echo "Missing required tools for this repository:"
    for item in "${missing[@]}"; do
        cmd="${item%%|*}"
        reason="${item#*|}"
        echo "  - $cmd ($reason)"
    done
    exit 1
fi

echo "Toolchain preflight passed."
