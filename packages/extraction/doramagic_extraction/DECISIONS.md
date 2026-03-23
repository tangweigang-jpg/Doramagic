# Stage15 Agentic Decisions

## 1. Mock-first agent loop

Round 1 赛马环境不接真实 LLM，也不读取真实仓库，因此 `stage15_agentic` 采用 deterministic mock loop：

- 工具轨迹只从 `repo_facts`、`stage1_output.findings`、`stage1_output.hypotheses` 推导
- 所有输出在相同输入下稳定，可重复回放
- 真实工具集成留到后续实现轮，不污染当前 contract

## 2. Evidence-first claims

`confirmed` claim 只允许由已有 `file_line` 证据推动。若没有 `file:line` 级证据，则 claim 最多写成 `pending`，绝不伪造确认结论。

## 3. Stable IDs and fixed artifacts

- `claim_id` 固定为 `C-{REPO_ID}-{NNN}`
- 中间文件名严格冻结为：
  - `hypotheses.jsonl`
  - `exploration_log.jsonl`
  - `claim_ledger.jsonl`
  - `evidence_index.json`
  - `context_digest.md`
- artifact 相对路径固定为 `artifacts/stage15/`

## 4. Budget semantics

- `max_tool_calls` 视为硬 budget
- `max_prompt_tokens` 视为软 budget，按 mock 轨迹文本长度估算 token
- `stop_after_no_gain_rounds` 用于连续无新 claim 时提前停止

## 5. Rejected claim handling

当假说与 Stage 1 finding 明确冲突时，必须生成 `rejected` claim 写入 `claim_ledger.jsonl`，避免“静默失败”。
