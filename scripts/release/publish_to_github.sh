#!/bin/bash
set -euo pipefail

# ─── Doramagic: Publish to GitHub ────────────────────────────────
# Trunk-Based Development: main → Gitea (full), filtered → GitHub (clean)
#
# Usage:
#   ./scripts/release/publish_to_github.sh v9.1.0
#   ./scripts/release/publish_to_github.sh v9.1.0 --dry-run
# ──────────────────────────────────────────────────────────────────

VERSION="${1:-}"
DRY_RUN=false
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=true

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version> [--dry-run]"
    echo "  e.g. $0 v9.1.0"
    exit 1
fi

# Validate semver format
if ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Version must be semver format: vX.Y.Z (got: $VERSION)"
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "═══════════════════════════════════════════"
echo "  Doramagic Release: $VERSION"
echo "═══════════════════════════════════════════"

# ─── Step 1: Pre-flight checks ───────────────────────────────────

echo ""
echo "▶ Step 1: Pre-flight checks"

# Must be on main branch
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "main" ]]; then
    echo "  ERROR: Must be on 'main' branch (currently on '$BRANCH')"
    exit 1
fi

# Working tree must be clean
if [[ -n "$(git status --porcelain)" ]]; then
    echo "  ERROR: Working tree is dirty. Commit or stash changes first."
    git status --short
    exit 1
fi

echo "  ✓ On main branch, working tree clean"

# ─── Step 2: Run tests ───────────────────────────────────────────

echo ""
echo "▶ Step 2: Running tests"

if [[ -f "Makefile" ]] && grep -q "^test:" Makefile; then
    make test || { echo "  ERROR: Tests failed. Fix before releasing."; exit 1; }
    echo "  ✓ Tests passed"
else
    echo "  ⚠ No test target in Makefile, skipping"
fi

# ─── Step 3: Build clean export ──────────────────────────────────

# ─── Step 2.5: Package self-contained skill ──────────────────────

echo ""
echo "▶ Step 2.5: Packaging self-contained skill"

PACKAGE_SCRIPT="$PROJECT_ROOT/scripts/release/package_skill.sh"
if [[ -x "$PACKAGE_SCRIPT" ]]; then
    bash "$PACKAGE_SCRIPT"
    echo "  ✓ Skill packaged"
    # Commit packaged skill if changed
    if [[ -n "$(git status --porcelain skills/doramagic/)" ]]; then
        git add skills/doramagic/
        git commit -q -m "chore: package self-contained skill for release"
        echo "  ✓ Packaged skill committed"
    fi
else
    echo "  ⚠ package_skill.sh not found, skipping"
fi

echo ""
echo "▶ Step 3: Building clean export"

CLEAN_DIR=$(mktemp -d)
trap "rm -rf $CLEAN_DIR" EXIT

# Export current HEAD (respects .gitignore)
git archive HEAD | tar -x -C "$CLEAN_DIR"

# Remove internal-only directories
INTERNAL_DIRS=(
    "research"
    "experiments"
    "races"
    "runs"
    "reports"
    "docs/brainstorm"
    "docs/plans"
    "docs/experiments"
    "docs/designs"
    "docs/logs"
    "docs/pitfalls.md"
    "_deprecated_variants"
    ".claire"
    ".claude"
    "openclaw-test"
    "packages/doramagic_product"
    "apps"
)

for dir in "${INTERNAL_DIRS[@]}"; do
    if [[ -d "$CLEAN_DIR/$dir" ]]; then
        rm -rf "$CLEAN_DIR/$dir"
        echo "  - Removed $dir/"
    fi
done

# Remove internal-only files
INTERNAL_FILES=(
    "INDEX.md"
    "TODOS.md"
    "doramagic.py"
    "doramagic_sonnet.py"
    "doramagic_gemini.py"
)

for f in "${INTERNAL_FILES[@]}"; do
    if [[ -f "$CLEAN_DIR/$f" ]]; then
        rm -f "$CLEAN_DIR/$f"
        echo "  - Removed $f"
    fi
done

# ─── Step 4: Verify community standard files ─────────────────────

echo ""
echo "▶ Step 4: Checking community standard files"

REQUIRED_FILES=(
    "README.md"
    "LICENSE"
    "CHANGELOG.md"
    "CONTRIBUTING.md"
    "SECURITY.md"
    "INSTALL.md"
    ".env.example"
    ".gitignore"
)

MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$CLEAN_DIR/$f" ]]; then
        echo "  ✓ $f"
    else
        echo "  ✗ MISSING: $f"
        MISSING=1
    fi
done

if [[ $MISSING -eq 1 ]]; then
    echo ""
    echo "  ERROR: Missing required community files. Add them before releasing."
    exit 1
fi

# ─── Step 5: Update version in CHANGELOG ─────────────────────────

echo ""
echo "▶ Step 5: Version stamp"

FILE_COUNT=$(find "$CLEAN_DIR" -type f | wc -l | tr -d ' ')
BRICK_COUNT=0
if [[ -d "$CLEAN_DIR/bricks" ]]; then
    BRICK_COUNT=$(cat "$CLEAN_DIR/bricks"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
fi

echo "  Files for release: $FILE_COUNT"
echo "  Bricks: $BRICK_COUNT"
echo "  Version: $VERSION"

# ─── Step 6: Push to GitHub ──────────────────────────────────────

echo ""
echo "▶ Step 6: Push to GitHub"

if $DRY_RUN; then
    echo "  [DRY RUN] Would push $FILE_COUNT files as $VERSION to GitHub"
    echo "  Clean export at: $CLEAN_DIR"
    # Don't cleanup in dry-run so user can inspect
    trap - EXIT
    echo ""
    echo "  Inspect with: ls $CLEAN_DIR"
    exit 0
fi

cd "$CLEAN_DIR"
git init -q
git add -A
git commit -q -m "Release $VERSION

Doramagic $VERSION
- $BRICK_COUNT knowledge bricks across $(ls bricks/*.jsonl 2>/dev/null | wc -l | tr -d ' ') domains
- Full dual-layer fusion pipeline (Phase A through H)
- Model-agnostic design (Claude, Gemini, GPT, Ollama)

Published from trunk via publish_to_github.sh"

git tag "$VERSION"

# Check if github remote exists in the original repo
cd "$PROJECT_ROOT"
GITHUB_URL=$(git remote get-url github 2>/dev/null || echo "")

if [[ -z "$GITHUB_URL" ]]; then
    echo "  ERROR: No 'github' remote configured. Add it with:"
    echo "    git remote add github https://github.com/tangweigang-jpg/Doramagic.git"
    exit 1
fi

cd "$CLEAN_DIR"
git remote add github "$GITHUB_URL"
git push github HEAD:main --force
git push github "$VERSION"

echo ""
echo "═══════════════════════════════════════════"
echo "  ✓ Published $VERSION to GitHub"
echo "  URL: https://github.com/tangweigang-jpg/Doramagic/releases/tag/$VERSION"
echo "═══════════════════════════════════════════"

# ─── Step 7: Tag in source repo too ──────────────────────────────

cd "$PROJECT_ROOT"
git tag "$VERSION" 2>/dev/null && echo "  ✓ Tagged $VERSION in local repo" || echo "  ⚠ Tag $VERSION already exists locally"
git push origin "$VERSION" 2>/dev/null && echo "  ✓ Pushed tag to Gitea" || echo "  ⚠ Could not push tag to Gitea"

# ─── Step 8: Publish to ClawHub ─────────────────────────────────

echo ""
echo "▶ Step 8: Publish to ClawHub"

SEMVER="${VERSION#v}"  # strip leading 'v' for clawhub (12.3.0 not v12.3.0)
SKILL_DIR="$PROJECT_ROOT/skills/doramagic"

if [[ ! -d "$SKILL_DIR" ]]; then
    echo "  ⚠ skills/doramagic not found, skipping ClawHub publish"
else
    if command -v npx &>/dev/null; then
        # 发布到两个 slug（历史原因：dora 和 doramagic 都有用户安装）
        for SLUG in dora doramagic; do
            echo "  Publishing ${SLUG}@$SEMVER to ClawHub..."
            npx clawhub@latest publish "$SKILL_DIR" \
                --slug "$SLUG" \
                --name "Doramagic" \
                --version "$SEMVER" \
                --changelog "Release $VERSION" \
                --tags latest 2>&1 | tail -1

            if [[ $? -eq 0 ]]; then
                echo "  ✓ Published ${SLUG}@$SEMVER"
            else
                echo "  ⚠ ${SLUG} publish failed (non-blocking)"
            fi
        done
        echo "  Note: skills may be hidden for a few minutes during security scan"
    else
        echo "  ⚠ npx not found, skipping ClawHub publish"
        echo "  Manual: npx clawhub@latest publish skills/doramagic --slug dora --version $SEMVER"
        echo "  Manual: npx clawhub@latest publish skills/doramagic --slug doramagic --version $SEMVER"
    fi
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  Release $VERSION complete"
echo "  GitHub: https://github.com/tangweigang-jpg/Doramagic/releases/tag/$VERSION"
echo "  ClawHub: https://clawhub.ai/skills/dora"
echo "═══════════════════════════════════════════"
