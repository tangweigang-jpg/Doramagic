#!/bin/bash
# Deploy Doramagic unified pipeline to Mac mini
#
# Usage: bash scripts/dev/deploy_to_macmini.sh
#
# What it does:
# 1. rsync packages/ to Mac mini
# 2. rsync new entry point (doramagic_main.py) to skill scripts/
# 3. rsync bricks/ and config files
# 4. Update SKILL.md on Mac mini

set -euo pipefail

REMOTE="tangsir@192.168.1.104"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_SKILL="~/.openclaw/skills/soul-extractor"
REMOTE_PACKAGES="~/Doramagic-racer/packages"

echo "=== Doramagic Deploy to Mac mini ==="
echo "Local:  $LOCAL_ROOT"
echo "Remote: $REMOTE"
echo ""

# 1. Sync packages/ (the core codebase)
echo "[1/5] Syncing packages/..."
rsync -avzu --delete \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='.ruff_cache' \
    "$LOCAL_ROOT/packages/" \
    "$REMOTE:$REMOTE_PACKAGES/"

# 2. Sync new entry point to skill scripts/
echo "[2/5] Syncing entry point..."
rsync -avzu \
    "$LOCAL_ROOT/skills/doramagic/scripts/doramagic_main.py" \
    "$REMOTE:$REMOTE_SKILL/scripts/"

# 3. Sync bricks and config
echo "[3/5] Syncing bricks and config..."
rsync -avzu \
    "$LOCAL_ROOT/bricks/" \
    "$REMOTE:~/Doramagic-racer/bricks/"
rsync -avzu \
    "$LOCAL_ROOT/models.json" \
    "$LOCAL_ROOT/platform_rules.json" \
    "$REMOTE:~/Doramagic-racer/"

# 4. Update SKILL.md
echo "[4/5] Updating SKILL.md..."
rsync -avzu \
    "$LOCAL_ROOT/skills/doramagic/SKILL.md" \
    "$REMOTE:$REMOTE_SKILL/"

# 5. Verify on remote
echo "[5/5] Verifying..."
ssh "$REMOTE" "
    cd ~/Doramagic-racer && \
    PYTHONPATH='packages/contracts:packages/controller:packages/shared_utils:packages/executors:packages/cross_project:packages/extraction:packages/orchestration:packages/skill_compiler:packages/platform_openclaw:packages/community' \
    python3 -c '
from doramagic_controller.flow_controller import FlowController
from doramagic_executors import ALL_EXECUTORS
print(f\"FlowController OK, {len(ALL_EXECUTORS)} executors registered\")
'
"

echo ""
echo "=== Deploy complete ==="
echo "Test with: ssh $REMOTE 'cd ~/Doramagic-racer && python3 packages/controller/doramagic_controller/../../../skills/doramagic/scripts/doramagic_main.py --cli --input \"帮我做记账app\"'"
