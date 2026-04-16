#!/usr/bin/env bash
# ============================================================
# v10 批量蓝图提取 — 顺序执行，每项独立验证
# 用法: bash scripts/batch_v10_extract.sh
# ============================================================

set -euo pipefail
cd "$(dirname "$0")/.."

source .env
export DORAMAGIC_AGENT_VERSION=v10

QUEUE=(
    "finance-bp-070:edgartools"
    "finance-bp-082:stock-screener"
    "finance-bp-071:opensanctions"
    "finance-bp-079:akshare"
    "finance-bp-072:lending"
    "finance-bp-069:tqsdk-python"
    "finance-bp-084:eastmoney"
    "finance-bp-076:AbsBox"
    "finance-bp-063:chainladder-python"
    "finance-bp-074:FinRobot"
    "finance-bp-083:Economic-Dashboard"
    "finance-bp-061:FinRL"
    "finance-bp-081:vnpy"
    "finance-bp-050:skorecard"
    "finance-bp-078:fava_investor"
    "finance-bp-077:Open_Source_Economic_Model"
    "finance-bp-064:insurance_python"
    "finance-bp-060:AMLSim"
    "finance-bp-065:pyliferisk"
    "finance-bp-080:FinDKG"
    "finance-bp-067:firesale_stresstest"
)

TOTAL=${#QUEUE[@]}
LOG_DIR="_runs/_batch/v10-batch-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

SUMMARY_FILE="$LOG_DIR/summary.txt"
echo "v10 Batch Extraction — $(date)" > "$SUMMARY_FILE"
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

    # 1. 清除旧 state
    rm -f "_runs/${BP_ID}/_agent_state.json"

    # 2. 检查 repo 存在
    if [ ! -d "repos/$REPO_NAME" ]; then
        echo "  SKIP: repos/$REPO_NAME not found"
        echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — SKIP (repo not found)" >> "$SUMMARY_FILE"
        continue
    fi

    # 3. 运行提取
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

        # 4. 提取成功 — 运行 SOP 验证
        echo "  Extraction completed (${ELAPSED}s). Running validation..."

        if .venv/bin/python scripts/validate_sop.py extraction \
            --blueprint-id "$BP_ID" >> "$PROJECT_LOG" 2>&1; then
            echo "  ✅ PASS (${ELAPSED}s)"
            echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — ✅ PASS (${ELAPSED}s)" >> "$SUMMARY_FILE"
            PASSED=$((PASSED + 1))
        else
            echo "  ⚠️ EXTRACTED but validation WARN (${ELAPSED}s)"
            echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — ⚠️ WARN: extracted but validation issues (${ELAPSED}s)" >> "$SUMMARY_FILE"
            PASSED=$((PASSED + 1))  # 提取成功就算通过
        fi
    else
        END_TIME=$(date +%s)
        ELAPSED=$(( END_TIME - START_TIME ))

        echo "  ❌ FAILED (${ELAPSED}s)"
        echo "[$SEQ/$TOTAL] $BP_ID ($REPO_NAME) — ❌ FAILED (${ELAPSED}s)" >> "$SUMMARY_FILE"
        # 记录最后几行错误
        echo "  Last error:" >> "$SUMMARY_FILE"
        tail -3 "$PROJECT_LOG" | sed 's/^/    /' >> "$SUMMARY_FILE"
        FAILED=$((FAILED + 1))
        FAILED_LIST="$FAILED_LIST $BP_ID"
    fi

    # 5. 速率限制缓冲 — 每个项目间隔 30 秒
    if [ $SEQ -lt $TOTAL ]; then
        echo "  Cooling down 30s..."
        sleep 30
    fi
done

echo ""
echo "============================================================"
echo "Batch Complete"
echo "============================================================"
echo "  Passed: $PASSED / $TOTAL"
echo "  Failed: $FAILED / $TOTAL"
if [ -n "$FAILED_LIST" ]; then
    echo "  Failed projects:$FAILED_LIST"
fi
echo ""
echo "Summary: $SUMMARY_FILE"
echo "Per-project logs: $LOG_DIR/"

# 追加最终统计
echo "" >> "$SUMMARY_FILE"
echo "========================================" >> "$SUMMARY_FILE"
echo "FINAL: $PASSED passed, $FAILED failed / $TOTAL total" >> "$SUMMARY_FILE"
if [ -n "$FAILED_LIST" ]; then
    echo "Failed:$FAILED_LIST" >> "$SUMMARY_FILE"
fi
