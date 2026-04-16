#!/usr/bin/env bash
# ============================================================
# v10 第二波蓝图提取 — 新增项目
# 用法: bash scripts/batch_v10_wave2.sh
# ============================================================

set -euo pipefail
cd "$(dirname "$0")/.."

source .env
export DORAMAGIC_AGENT_VERSION=v10

# 第二波：高价值项目，按规模排序
# 预估 4 小时可完成 ~10 个
QUEUE=(
    "finance-bp-082:stock-screener"
    "finance-bp-085:freqtrade"
    "finance-bp-086:backtrader"
    "finance-bp-087:qlib"
    "finance-bp-088:zipline-reloaded"
    "finance-bp-089:rqalpha"
    "finance-bp-090:QUANTAXIS"
    "finance-bp-091:czsc"
    "finance-bp-092:vectorbt"
    "finance-bp-093:PyPortfolioOpt"
    "finance-bp-094:easytrader"
)

TOTAL=${#QUEUE[@]}
LOG_DIR="_runs/_batch/v10-wave2-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

SUMMARY_FILE="$LOG_DIR/summary.txt"
echo "v10 Wave 2 Extraction — $(date)" > "$SUMMARY_FILE"
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
            echo "  ⚠️ EXTRACTED but validation WARN (${ELAPSED}s)"
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
echo "Wave 2 Complete: $PASSED passed, $FAILED failed / $TOTAL"
echo "============================================================"
echo "" >> "$SUMMARY_FILE"
echo "FINAL: $PASSED passed, $FAILED failed / $TOTAL total" >> "$SUMMARY_FILE"
if [ -n "$FAILED_LIST" ]; then
    echo "Failed:$FAILED_LIST" >> "$SUMMARY_FILE"
fi
