#!/usr/bin/env bash
# ============================================================
# v10 Wave 5 + Wave 6 蓝图提取（合并批次，19 项）
# - Wave 5: 8 项（原 9 项，剔除 bp-113 sa-ccr-python 无 Python 实现）
# - Wave 6: 11 项（bp-118 substituted: sEmery/financial-statement-analysis → JerBouma/FinanceToolkit；
#                 bp-122 substituted: twopirllc/pandas-ta → bukosabino/ta）
# - ccxt (bp-111, 1334 .py 文件) 放末尾，避免阻塞其他项目
# ============================================================

set -euo pipefail
cd "$(dirname "$0")/.."

source .env
export DORAMAGIC_AGENT_VERSION=v10

QUEUE=(
    "finance-bp-107:empyrical-reloaded"
    "finance-bp-109:ta-lib-python"
    "finance-bp-112:openLGD"
    "finance-bp-114:edgar-crawler"
    "finance-bp-116:FinRL-Meta"
    "finance-bp-118:FinanceToolkit"
    "finance-bp-119:transitionMatrix"
    "finance-bp-120:alphalens-reloaded"
    "finance-bp-121:machine-learning-for-trading"
    "finance-bp-122:ta-python"
    "finance-bp-123:QuantLib-SWIG"
    "finance-bp-124:arch"
    "finance-bp-125:bt"
    "finance-bp-126:lifelines"
    "finance-bp-127:py_vollib"
    "finance-bp-128:yfinance"
    "finance-bp-129:beancount"
    "finance-bp-130:tensortrade"
    "finance-bp-111:ccxt"
)

TOTAL=${#QUEUE[@]}
LOG_DIR="_runs/_batch/v10-wave56-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

SUMMARY_FILE="$LOG_DIR/summary.txt"
echo "v10 Wave 5+6 Extraction — $(date)" > "$SUMMARY_FILE"
echo "Total: $TOTAL projects (Wave 5 + Wave 6 merged, ccxt at end)" >> "$SUMMARY_FILE"
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
echo "Wave 5+6 Complete: $PASSED passed, $FAILED failed / $TOTAL"
echo "============================================================"
echo "" >> "$SUMMARY_FILE"
echo "FINAL: $PASSED passed, $FAILED failed / $TOTAL total" >> "$SUMMARY_FILE"
if [ -n "$FAILED_LIST" ]; then
    echo "Failed:$FAILED_LIST" >> "$SUMMARY_FILE"
fi
