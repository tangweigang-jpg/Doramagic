#!/bin/bash
set -euo pipefail

# ─── Doramagic: Package self-contained skill ─────────────────────
# Copies packages/, bricks/, and config into skills/doramagic/
# so the skill works standalone when installed via cp -r.
#
# Usage:
#   ./scripts/release/package_skill.sh
# ──────────────────────────────────────────────────────────────────

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_DIR="$PROJECT_ROOT/skills/doramagic"

echo "Packaging self-contained skill..."
echo "  Source: $PROJECT_ROOT"
echo "  Target: $SKILL_DIR"

# ─── Copy packages/ ──────────────────────────────────────────────
# Only copy runtime packages (skip test-only, experimental)
RUNTIME_PACKAGES=(
    contracts
    controller
    community
    cross_project
    domain_graph
    executors
    extraction
    orchestration
    platform_openclaw
    shared_utils
    skill_compiler
)

# Clean previous packaging
rm -rf "$SKILL_DIR/packages"
mkdir -p "$SKILL_DIR/packages"

for pkg in "${RUNTIME_PACKAGES[@]}"; do
    src="$PROJECT_ROOT/packages/$pkg"
    if [[ -d "$src" ]]; then
        # Copy only Python source, skip tests and __pycache__
        rsync -a \
            --exclude='tests/' \
            --exclude='__pycache__/' \
            --exclude='*.pyc' \
            "$src/" "$SKILL_DIR/packages/$pkg/"
        echo "  + packages/$pkg"
    else
        echo "  ! MISSING: packages/$pkg"
    fi
done

# ─── Copy bricks/ ────────────────────────────────────────────────
rm -rf "$SKILL_DIR/bricks"
mkdir -p "$SKILL_DIR/bricks"
cp "$PROJECT_ROOT/bricks/"*.jsonl "$SKILL_DIR/bricks/"
BRICK_COUNT=$(cat "$SKILL_DIR/bricks/"*.jsonl | wc -l | tr -d ' ')
echo "  + bricks/ ($BRICK_COUNT bricks)"

# ─── Copy config files ───────────────────────────────────────────
cp "$PROJECT_ROOT/platform_rules.json" "$SKILL_DIR/platform_rules.json"
echo "  + platform_rules.json"

if [[ -f "$PROJECT_ROOT/models.json.example" ]]; then
    cp "$PROJECT_ROOT/models.json.example" "$SKILL_DIR/models.json.example"
    echo "  + models.json.example"
fi

# ─── Verify ──────────────────────────────────────────────────────
echo ""
echo "Verification:"
PKG_COUNT=$(ls -d "$SKILL_DIR/packages/"*/ 2>/dev/null | wc -l | tr -d ' ')
echo "  Packages: $PKG_COUNT"
echo "  Bricks: $BRICK_COUNT"
echo "  Scripts: $(ls "$SKILL_DIR/scripts/"*.py 2>/dev/null | wc -l | tr -d ' ')"

TOTAL_FILES=$(find "$SKILL_DIR" -type f -not -name '*.pyc' -not -path '*__pycache__*' | wc -l | tr -d ' ')
echo "  Total files: $TOTAL_FILES"
echo ""
echo "Done. Skill packaged at: $SKILL_DIR"
