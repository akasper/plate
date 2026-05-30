#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-20}"
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 [limit]" >&2
  exit 1
fi

gh issue list --state open --limit "$LIMIT" --json number,title,labels,url \
  --jq '.[] | select(any(.labels[]?; .name == "Question" or .name == "#question")) | "\(.number)\t\(.title)\t\(.url)"'
