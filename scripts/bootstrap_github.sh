#!/usr/bin/env bash
# Bootstrap a new PLATE repository using the GitHub CLI.
#
# Syncs canonical labels, removes conflicting default GitHub labels, replaces
# the CODEOWNERS placeholder, enables delete-branch-on-merge by default,
# applies
# conservative baseline branch protection, and optionally initializes the wiki.
#
# Requirements: gh (GitHub CLI) >= 2.x, git, awk, sed
# Works on macOS, Linux, and Windows Subsystem for Linux.

set -euo pipefail

REPO=""
LOCAL_REPO="."
OWNER_HANDLE=""
REMOVE_DEFAULT_LABELS=false
SET_DELETE_BRANCH_ON_MERGE=true
SKIP_DELETE_BRANCH_ON_MERGE=false
DELETE_BRANCH_ON_MERGE_FLAG_SET=false
PROTECT_BRANCH=""
INIT_WIKI=false

DEFAULT_LABELS_TO_REMOVE=(
    "bug"
    "documentation"
    "duplicate"
    "enhancement"
    "good first issue"
    "help wanted"
    "invalid"
    "question"
    "wontfix"
)

usage() {
    cat <<EOF
Usage: $(basename "$0") --repo OWNER/REPO [options]

Options:
  --repo OWNER/REPO             GitHub repository in OWNER/REPO format (required)
  --local-repo PATH             Path to local repository checkout (default: .)
  --owner-handle HANDLE         GitHub username or team for CODEOWNERS (e.g. @your-username)
  --remove-default-labels       Delete conflicting default GitHub labels
  --set-delete-branch-on-merge  Enable delete-branch-on-merge (default)
  --skip-delete-branch-on-merge Leave merged branches in place
  --protect-branch BRANCH       Apply conservative baseline protection to BRANCH
  --init-wiki                   Initialize the wiki from docs/wiki/Home.md
  -h, --help                    Show this help message
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) REPO="$2"; shift 2 ;;
        --local-repo) LOCAL_REPO="$2"; shift 2 ;;
        --owner-handle) OWNER_HANDLE="$2"; shift 2 ;;
        --remove-default-labels) REMOVE_DEFAULT_LABELS=true; shift ;;
        --set-delete-branch-on-merge)
            if $DELETE_BRANCH_ON_MERGE_FLAG_SET && $SKIP_DELETE_BRANCH_ON_MERGE; then
                echo "Error: --set-delete-branch-on-merge and --skip-delete-branch-on-merge cannot be used together." >&2
                exit 1
            fi
            SET_DELETE_BRANCH_ON_MERGE=true
            DELETE_BRANCH_ON_MERGE_FLAG_SET=true
            shift
            ;;
        --skip-delete-branch-on-merge)
            if $DELETE_BRANCH_ON_MERGE_FLAG_SET && $SET_DELETE_BRANCH_ON_MERGE; then
                echo "Error: --set-delete-branch-on-merge and --skip-delete-branch-on-merge cannot be used together." >&2
                exit 1
            fi
            SET_DELETE_BRANCH_ON_MERGE=false
            SKIP_DELETE_BRANCH_ON_MERGE=true
            DELETE_BRANCH_ON_MERGE_FLAG_SET=true
            shift
            ;;
        --protect-branch) PROTECT_BRANCH="$2"; shift 2 ;;
        --init-wiki) INIT_WIKI=true; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown argument: $1" >&2; usage ;;
    esac
done

if [[ -z "$REPO" ]]; then
    echo "Error: --repo is required." >&2
    usage
fi

LOCAL_REPO="$(cd "$LOCAL_REPO" && pwd)"
LABELS_PATH="$LOCAL_REPO/.github/labels.yml"

if [[ ! -f "$LABELS_PATH" ]]; then
    echo "Error: Label registry not found: $LABELS_PATH" >&2
    exit 1
fi

gh auth status

# parse_labels outputs "name|color|description" for each label entry in labels.yml.
parse_labels() {
    awk '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        /^- name:/ {
            if (name != "") print name "|" color "|" desc
            name = $0
            sub(/^- name:[[:space:]]*"?/, "", name)
            sub(/"?[[:space:]]*$/, "", name)
            color = ""; desc = ""
        }
        /^[[:space:]]+color:/ {
            color = $0
            sub(/^[[:space:]]*color:[[:space:]]*"?/, "", color)
            sub(/"?[[:space:]]*$/, "", color)
        }
        /^[[:space:]]+description:/ {
            desc = $0
            sub(/^[[:space:]]*description:[[:space:]]*"?/, "", desc)
            sub(/"?[[:space:]]*$/, "", desc)
        }
        END { if (name != "") print name "|" color "|" desc }
    ' "$LABELS_PATH"
}

# GitHub label descriptions are limited to 100 characters.
GITHUB_LABEL_DESC_MAX=100

clamp_label_description() {
    local desc="$1"
    local len=${#desc}
    if (( len > GITHUB_LABEL_DESC_MAX )); then
        echo "Warning: label description is ${len} chars (GitHub max ${GITHUB_LABEL_DESC_MAX}); truncating for API." >&2
        desc="${desc:0:GITHUB_LABEL_DESC_MAX}"
    fi
    printf '%s' "$desc"
}

# Sync canonical labels ----------------------------------------------------------

echo "Syncing canonical labels..."
LABEL_SYNC_OK=0
LABEL_SYNC_FAILED=0
CANONICAL_NAMES=()

# Fetch all existing labels once as "lowercase|actualname" pairs.
EXISTING_LABELS_FILE=$(mktemp)
trap 'rm -f "$EXISTING_LABELS_FILE"' EXIT

gh label list --repo "$REPO" --limit 200 --json name \
    --jq '.[] | ((.name | ascii_downcase) + "|" + .name)' \
    > "$EXISTING_LABELS_FILE"

while IFS='|' read -r label_name label_color label_desc; do
    CANONICAL_NAMES+=("$label_name")
    label_lower=$(echo "$label_name" | tr '[:upper:]' '[:lower:]')
    label_desc=$(clamp_label_description "$label_desc")

    # Find the actual existing name (case-insensitive lookup).
    actual_name=$(awk -F'|' -v target="$label_lower" '$1 == target {print substr($0, index($0, "|")+1); exit}' "$EXISTING_LABELS_FILE")

    if [[ -n "$actual_name" ]]; then
        if gh label edit "$actual_name" \
            --repo "$REPO" \
            --name "$label_name" \
            --color "$label_color" \
            --description "$label_desc"; then
            LABEL_SYNC_OK=$((LABEL_SYNC_OK + 1))
        else
            echo "Error: failed to update label '${label_name}' (see gh output above)." >&2
            LABEL_SYNC_FAILED=$((LABEL_SYNC_FAILED + 1))
        fi
    else
        if gh label create "$label_name" \
            --repo "$REPO" \
            --color "$label_color" \
            --description "$label_desc"; then
            LABEL_SYNC_OK=$((LABEL_SYNC_OK + 1))
        else
            echo "Error: failed to create label '${label_name}' (see gh output above)." >&2
            LABEL_SYNC_FAILED=$((LABEL_SYNC_FAILED + 1))
        fi
    fi
done < <(parse_labels)

echo "Synced $LABEL_SYNC_OK canonical labels (${LABEL_SYNC_FAILED} failed)."
if [[ "$LABEL_SYNC_FAILED" -gt 0 ]]; then
    echo "Error: label sync failed for ${LABEL_SYNC_FAILED} label(s)." >&2
    exit 1
fi

# Remove default GitHub labels ---------------------------------------------------

if $REMOVE_DEFAULT_LABELS; then
    canonical_lower=$(printf '%s\n' "${CANONICAL_NAMES[@]}" | tr '[:upper:]' '[:lower:]')

    for default_label in "${DEFAULT_LABELS_TO_REMOVE[@]}"; do
        # Skip if it matches a canonical label name.
        if echo "$canonical_lower" | grep -qxF "$default_label"; then
            continue
        fi
        # Only delete if the label actually exists in the repository.
        actual_name=$(awk -F'|' -v target="$default_label" '$1 == target {print substr($0, index($0, "|")+1); exit}' "$EXISTING_LABELS_FILE")
        if [[ -n "$actual_name" ]]; then
            gh label delete "$actual_name" --repo "$REPO" --yes
        fi
    done
    echo "Removed conflicting default GitHub labels."
fi

# Replace CODEOWNERS placeholder -------------------------------------------------

if [[ -n "$OWNER_HANDLE" ]]; then
    codeowners_path="$LOCAL_REPO/.github/CODEOWNERS"
    if [[ -f "$codeowners_path" ]]; then
        if grep -q "@PLATE_REPO_OWNER" "$codeowners_path"; then
            sed "s|@PLATE_REPO_OWNER|$OWNER_HANDLE|g" "$codeowners_path" > "${codeowners_path}.tmp"
            mv "${codeowners_path}.tmp" "$codeowners_path"
            echo "Updated .github/CODEOWNERS with the provided owner handle."
        else
            echo ".github/CODEOWNERS already uses the requested owner handle."
        fi
    fi
fi

# Enable delete-branch-on-merge --------------------------------------------------

if $SET_DELETE_BRANCH_ON_MERGE; then
    gh repo edit "$REPO" --delete-branch-on-merge
    echo "Enabled delete-branch-on-merge."
elif $SKIP_DELETE_BRANCH_ON_MERGE; then
    echo "Skipped delete-branch-on-merge per flag."
fi

# Apply baseline branch protection -----------------------------------------------

if [[ -n "$PROTECT_BRANCH" ]]; then
    gh api \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        "repos/$REPO/branches/$PROTECT_BRANCH/protection" \
        --input - <<'PROTECTION_JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
PROTECTION_JSON
    echo "Applied baseline protection to $PROTECT_BRANCH."
fi

# Initialize wiki ----------------------------------------------------------------

if $INIT_WIKI; then
    wiki_source="$LOCAL_REPO/docs/wiki/Home.md"
    if [[ ! -f "$wiki_source" ]]; then
        echo "Error: Wiki source file not found: $wiki_source" >&2
        exit 1
    fi

    author_name=$(gh api user --jq '.name // .login')
    author_email=$(gh api user --jq '.email // (.login + "@users.noreply.github.com")')
    token=$(gh auth token)

    wiki_dir=$(mktemp -d)
    clone_url="https://github.com/${REPO}.wiki.git"
    GIT_ASKPASS_SCRIPT=$(mktemp)
    trap 'rm -rf "$wiki_dir"; rm -f "$EXISTING_LABELS_FILE" "$GIT_ASKPASS_SCRIPT"' EXIT
    printf "#!/bin/sh\necho '%s'\n" "$token" > "$GIT_ASKPASS_SCRIPT"
    chmod +x "$GIT_ASKPASS_SCRIPT"
    export GIT_ASKPASS="$GIT_ASKPASS_SCRIPT"
    export GIT_TERMINAL_PROMPT=0
    git -c credential.helper= clone "$clone_url" "$wiki_dir"
    cp "$wiki_source" "$wiki_dir/Home.md"

    if [[ -z "$(git -C "$wiki_dir" status --short)" ]]; then
        echo "Wiki homepage was already up to date."
    else
        git -C "$wiki_dir" config user.name "$author_name"
        git -C "$wiki_dir" config user.email "$author_email"
        git -C "$wiki_dir" add Home.md
        git -C "$wiki_dir" commit -m "docs: initialize wiki home page"
        git -c credential.helper= -C "$wiki_dir" push origin master
        echo "Initialized the wiki homepage from docs/wiki/Home.md."
    fi
    unset GIT_ASKPASS GIT_TERMINAL_PROMPT
fi

# Manual follow-up ---------------------------------------------------------------

echo ""
echo "Manual follow-up still required:"
echo "1. Replace placeholder product language in SPEC.md, CURRENT.md, and public-facing docs."
echo "2. Decide whether branch protection should also require approvals, code-owner review, status checks, or linear history."
echo "3. Configure GitHub Projects fields for planning state such as status, priority, owner, iteration, target date, and release target."
echo "4. Create the first real Epic milestone and, if needed, an optional companion Epic issue."
echo "5. Tune CI, release, pages, and audit workflows for the project stack."
echo "6. Decide whether to enable wiki sync and, if so, create PLATE_WIKI_SYNC_ENABLED and WIKI_TOKEN."
