#!/usr/bin/env bash
# ============================================================
# v10 Wave 4 蓝图提取 — 6 个高优先级项目
# 填补 ESG/碳因子、绩效归因、宏观多资产、加密量化、风险平价、金融 ML 6 个稀薄子域
# ============================================================

set -euo pipefail
cd "$(dirname "$0")/.."

source .env
export DORAMAGIC_AGENT_VERSION=v10

QUEUE=(
    "finance-bp-105:open-climate-investing"
    "finance-bp-106:pyfolio-reloaded"
    "finance-bp-108:finmarketpy"
    "finance-bp-110:cryptofeed"
    "finance-bp-115:mlfinlab"
    "finance-bp-117:Riskfolio-Lib"
)

TOTAL=${#QUEUE[@]}
LOG_DIR="_runs/_batch/v10-wave4-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

SUMMARY_FILE="$LOG_DIR/summary.txt"
echo "v10 Wave 4 Extraction — $(date)" > "$SUMMARY_FILE"
echo "Total: $TOTAL projects (high-priority subdomain fill-ins)" >> "$SUMMARY_FILE"
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
echo "Wave 4 Complete: $PASSED passed, $FAILED failed / $TOTAL"
echo "============================================================"
echo "" >> "$SUMMARY_FILE"
echo "FINAL: $PASSED passed, $FAILED failed / $TOTAL total" >> "$SUMMARY_FILE"
if [ -n "$FAILED_LIST" ]; then
    echo "Failed:$FAILED_LIST" >> "$SUMMARY_FILE"
fi
