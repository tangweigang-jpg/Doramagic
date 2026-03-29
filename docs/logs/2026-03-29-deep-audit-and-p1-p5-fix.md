# Doramagic 深度审计 + P1-P5 修复
日期: 2026-03-29
执行者: 赛马（Claude Code opus + Codex CLI gpt-5.4-mini）

## 做了什么

### 起因
用户在 OpenClaw 中测试 Doramagic，发现小 repo（几百行 C++）提取结果跑偏——输出的是通用英语学习建议而非设计智慧。触发了对项目的全面深度审计。

### 深度审计
- 后台监控代理（Sonnet）发现 Makefile 指向错误 Python、mypy 未安装、import 断裂等基础问题
- 标杆调研：分析了 gstack、skill-forge、investigate、capability-evolver、cso 5 个优质 skill
- 深度审计（Opus）：逐包审查 15 个子包，产出评分 A~F，识别 16 项风险

### 五个优先级修复

| 优先级 | 内容 | commits | 赛马 |
|--------|------|---------|------|
| P1 安全 | ReDoS 修复 + prompt 注入隔离(5处) + LLM 调用预算(max_llm_calls=50) | 2 | Claude + Codex（同目录，效果差） |
| P2 架构 | import anthropic → LLMAdapter + orchestration 废弃标记 | 2 | 仅 Claude（未赛马，已反思） |
| P3 代码质量 | flow_controller.py 1028行→4模块 + stage15_agentic.py 1292行→5模块 | 4 | 独立 clone 赛马 ✅ 交叉审查 ✅ |
| P4 测试 | 恢复 3 组安全测试 + FlowController 11 个单元测试 | 2 | 独立 clone 赛马 ✅ |
| P5 产品质量 | SynthesisRunner LLM 质量过滤 + 熔断机制 | 1 | Claude 完成，Codex(重试机制)进行中 |

### 测试覆盖提升
- 修复前：302 通过
- 修复后：484 通过（+60%）
- 新增：FlowController 11 个单元测试（从 0 到 11）
- 恢复：confidence_system + dsd 安全测试（133 个）

## 关键决策

### 1. 赛马隔离方案（为什么选 git clone 而非 worktree）
Codex sandbox 的 workspace-write 模式禁止写 `.git/` 目录。worktree 的 `.git/` 指向主仓库，同样被阻止。只有完全独立的 git clone（`.git/` 在 clone 自己目录内）才允许 Codex 执行 git checkout/add/commit。

### 2. orchestration 不能直接删
原计划删除 3716 行的废弃包，但发现 3 个活跃 executor（worker_supervisor、repo_worker、soul_extractor_batch）仍在 import `run_single_project_pipeline`。改为标记 DeprecationWarning + 文档声明。

### 3. doramagic_product 保留并整合（非废弃）
pipeline.py 有 7 项主架构缺少的独有能力（GitHub 直连评分、三层 Discovery 降级、启发式知识兜底、XML repo pack、synthesis URL 富化、compile_ready 过滤、四文件自渲染）。但整合方式必须是"能力模块插入 DAG 节点"而非"搬运线性流程"，否则会踩回"把产品当一次性脚本"的老坑。

### 4. 提取跑偏的根因
三个问题叠加：
- SynthesisRunner 纯机械搬运（0 个 LLM 调用），不做任何质量判断
- 小 repo 证据不足但没有熔断机制
- 编译阶段缺乏"素材太差拒绝产出"的逻辑

P5 修复了前两个：SynthesisRunner 加了 LLM 质量过滤 + 双重熔断。

## 遇到的问题

1. **ruff pre-commit 与中文文档字符串冲突**：RUF001/002/003 把中文全角标点标为错误。在 pyproject.toml 中全局 ignore 了这三条规则。
2. **per-file ignore 键重复导致 TOML 解析失败**：同一个文件在 `extend-per-file-ignores` 中出现两次会报 `duplicate key`。
3. **Codex 在同目录赛马互相踩脚**：P1 时 Codex 和 Claude 改了同一目录的同一文件，导致 diff 混乱。P3 起改用独立 clone 彻底解决。

## 踩坑记录

已追加到 docs/pitfalls.md（如有新坑）：
- 不要让 Codex 和 Claude Code 在同一个 git 工作目录赛马（因为 Codex sandbox 无法操作 .git/，且两边改动会互相覆盖，必须用独立 git clone 隔离）

## 下一步

1. Codex 的 LLMAdapter 重试机制完成后合并
2. doramagic_product 7 项能力的迁移设计文档
3. knowledge_compiler 24 个预存测试失败的修复
4. test_compiler.py 适配新 API（run_skill_compiler 已移除）
5. 71 处 sys.path.insert → editable install 迁移
6. 5 个 Gemini 变体合并为策略模式
