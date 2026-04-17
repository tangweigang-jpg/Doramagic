#!/usr/bin/env bash
# ============================================================
# v10 第三波蓝图提取 — 大型项目为主
# ============================================================

set -euo pipefail
cd "$(dirname "$0")/.."

source .env
export DORAMAGIC_AGENT_VERSION=v10

QUEUE=(
    "finance-bp-095:rotki"
    "finance-bp-096:hummingbot"
    "finance-bp-097:OpenBB"
    "finance-bp-098:nautilus_trader"
    "finance-bp-099:TradingAgents-CN"
    "finance-bp-100:LEAN"
    "finance-bp-101:FinancePy"
    "finance-bp-102:Darts"
    "finance-bp-103:ArcticDB"
    "finance-bp-104:Engine"
)

TOTAL=${#QUEUE[@]}
LOG_DIR="_runs/_batch/v10-wave3-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

SUMMARY_FILE="$LOG_DIR/summary.txt"
echo "v10 Wave 3 Extraction — $(date)" > "$SUMMARY_FILE"
echo "Total: $TOTAL projects" >> "$SUMMARY_FILE"
echo "========================================" >> "$SUMMARY_FILE"

PASSED=0
FAILED=0
FAILED_LIST=""

for i in "${!QUEUE[@]}"; do
    IFS=':' read -r BP_ID REPO_NAME <<< "${QUEUE[$i]}"
    SEQ=$((i + 1))

    echo ""
    echo "============================================================"
    echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME)"
    echo "============================================================"

    PROJECT_LOG="$LOG_DIR/${BP_ID}.log"
    rm -f "_runs/${BP_ID}/_agent_state.json"

    if [ ! -d "repos/$REPO_NAME" ]; then
        echo "  SKIP: repos/$REPO_NAME not found"
        echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — SKIP (repo not found)" >> "$SUMMARY_FILE"
        continue
    fi

    echo "  Starting extraction..."
    START_TIME=$(date +%s)

    if .venv/bin/python scripts/run_extraction_agent.py single \
        --blueprint-id "$BP_ID" \
        --repo-path "repos/$REPO_NAME" \
        --blueprint-version v5 \
        --skip-constraint \
        > "$PROJECT_LOG" 2>&1; then

        END_TIME=$(date +%s)
        ELAPSED=$(( END_TIME - START_TIME ))
        echo "  Extraction completed (${ELAPSED}s). Running validation..."

        if .venv/bin/python scripts/validate_sop.py extraction \
            --blueprint-id "$BP_ID" >> "$PROJECT_LOG" 2>&1; then
            echo "  ✅ PASS (${ELAPSED}s)"
            echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — ✅ PASS (${ELAPSED}s)" >> "$SUMMARY_FILE"
            PASSED=$((PASSED + 1))
        else
            echo "  ⚠️ WARN (${ELAPSED}s)"
            echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — ⚠️ WARN (${ELAPSED}s)" >> "$SUMMARY_FILE"
            PASSED=$((PASSED + 1))
        fi
    else
        END_TIME=$(date +%s)
        ELAPSED=$(( END_TIME - START_TIME ))
        echo "  ❌ FAILED (${ELAPSED}s)"
        echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — ❌ FAILED (${ELAPSED}s)" >> "$SUMMARY_FILE"
        tail -3 "$PROJECT_LOG" | sed 's/^/    /' >> "$SUMMARY_FILE"
        FAILED=$((FAILED + 1))
        FAILED_LIST="$FAILED_LIST $BP_ID"
    fi

    if [ $SEQ -lt $TOTAL ]; then
        echo "  Cooling down 30s..."
        sleep 30
    fi
done

echo ""
echo "============================================================"
echo "Wave 3 Complete: $PASSED passed, $FAILED failed / $TOTAL"
echo "============================================================"
echo "" >> "$SUMMARY_FILE"
echo "FINAL: $PASSED passed, $FAILED failed / $TOTAL total" >> "$SUMMARY_FILE"
if [ -n "$FAILED_LIST" ]; then
    echo "Failed:$FAILED_LIST" >> "$SUMMARY_FILE"
fi
