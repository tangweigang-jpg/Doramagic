# Doramagic OpenClaw 集成测试 — 全量问题报告
日期: 2026-03-30
执行者: Claude Code opus + sonnet 子代理

## 总结

今天对 Doramagic 在 OpenClaw/Telegram 中的端到端运行做了 7 次真实测试。
修复了 10+ 个基础设施问题后，Pipeline 可以跑通，但暴露了**产品层面的根本性问题**。

## 测试记录

| # | Run ID | 版本 | 模型 | 结果 | 耗时 | 问题 |
|---|--------|------|------|------|------|------|
| 1 | run-20260329-230455 | v12.1.4 | ? | DEGRADED | ? | 旧版，包导入失败 |
| 2 | run-20260330-005936 | v12.3.1 | wow3 | DEGRADED | 7min+ | setup_packages_path 误判，AI 手动修复 PYTHONPATH |
| 3 | run-20260330-092713 | v12.3.2 | wow3 | **挂起** | ∞ | Phase E LLM 调用无限等待 |
| 4 | run-20260330-094951 | v12.3.3 | wow3 | DEGRADED | 17s | 过滤器太严（name 匹配），0 候选 |
| 5 | run-20260330-095652 | v12.3.3+ | wow3 | DEGRADED | 17s | 过滤器 quality_signals 类型错误，stars 读成 0 |
| 6 | run-20260330-100052 | v12.3.3+ | wow3 | **DONE** ✓ | ~3min | 首次成功！但产出质量差（fallback 模板） |
| 7 | run-20260330-104552 | v12.3.3+ | MiniMax | **DONE** ✓ | ~2.5min | 成功但 OpenClaw agent 等不及被 terminated |
| 8 | run-20260330-110657 | v12.3.3+ | GLM-5 | DEGRADED | 30s | Phase D 降级（知识过滤后不够），--async 模式首次生效 |

## 已修复的问题（v12.3.1 → v12.3.3+）

### 基础设施层

| # | 问题 | 修复 | Commit |
|---|------|------|--------|
| 1 | setup_packages_path 误判 ~/.openclaw/ 为开发目录 | 增加 pyproject.toml/Makefile 存在性检查 | 608cc33 |
| 2 | 版本号硬编码 v12.1.2 | 从 SKILL.md 动态读取 | 38aabf2 |
| 3 | _brick_catalog_dir 路径错误 | 优先 env + 调整候选顺序 | 056f685 |
| 4 | Phase E LLM 无限挂起 | asyncio.wait_for(timeout=30) | 77321d9 |
| 5 | CI ignore 规则不同步 | 与 Makefile 同步 | 8ee24bf |
| 6 | quality_signals 是 Pydantic model 非 dict | getattr 读 stars | a3260bf |
| 7 | DORAMAGIC_BRICKS_DIR setdefault 不覆盖旧值 | 改 os.environ 显式赋值 | 77321d9 |

### 用户体验层

| # | 问题 | 修复 | Commit |
|---|------|------|--------|
| 8 | 过程反馈是英文（用户发中文） | SKILL.md 增加语言匹配指令 | ce41b54 |
| 9 | "Wait." "Wait again." 刷屏 10 条 | SKILL.md 限制只发 1 条等待消息 | ce41b54 |
| 10 | OpenClaw agent 等 2.5 分钟被 terminated | --async 模式 + /dora-status | 749751d |
| 11 | 原始 JSON 展示给用户 | SKILL.md 禁止显示 raw JSON | ce41b54 |

### 部署层

| # | 问题 | 修复 |
|---|------|------|
| 12 | bricks 目录未同步到 workspace | 手动 rsync + 发布脚本确认 |
| 13 | ~/.openclaw/packages/ 旧版残留 | 手动删除 |
| 14 | ~/.openclaw/skills/doramagic/ 旧版残留 | 手动删除 |

## 未解决的产品级问题（CRITICAL）

### P0：实时 GitHub 搜索是错误的产品路径

**表现**：
- china-dictatorship 反复出现在"英语学习"搜索结果中
- GitHub 搜索不是产品推荐引擎，无法根据用户意图找到合适工具
- 延迟 2-3 分钟不可接受
- 搜索结果不可控、不可预测

**根因**：实时搜索 GitHub 试图解决"帮用户找工具"的问题，但 GitHub API 的设计目标是"帮开发者找代码"，两者有本质差异。

**对比**：
| 路径 | 延迟 | 质量 | 可控性 |
|------|------|------|--------|
| BRICK_STITCH（知识积木直缝）| 秒级 | 高（预验证） | 完全可控 |
| GitHub 实时搜索 | 分钟级 | 低（垃圾混入） | 不可控 |

### P0：知识积木库没有覆盖终端用户场景

**表现**：49 个分类全部是技术框架（React、FastAPI、LangChain...），没有一个面向终端用户需求（英语学习、健康管理、旅行工具...）。

**影响**：BRICK_STITCH 路径在非技术需求面前完全失效，被迫走 GitHub 搜索 → 质量差。

### P1：LLM fallback 模板质量极差

**表现**：Phase E 在 LLM 不可用时走 fallback 模板，产出内容如：
- WHY: "Repository 'DashPlayer-main' written in TypeScript, JavaScript, Python"（这不是设计智慧）
- UNSAID: "Avoid breaking @ai-sdk/openai"（跟英语学习毫无关系）

**根因**：fallback 模板只是机械填充 repo metadata，没有任何语义理解。

### P1：wow3 平台不稳定

**表现**：测试期间 wow3 全平台故障——Claude Sonnet/Opus 返回 503，GPT-5.4/5.2 全部超时。

**影响**：Doramagic 的 LLM 功能（Phase A 翻译、Phase E 编译）完全依赖外部 LLM 服务，平台不稳定 = 产品不可用。

### P2：OpenClaw AI 在 Doramagic 降级时"越俎代庖"

**表现**：Doramagic 返回降级结果后，OpenClaw AI 自行充当产品顾问，推荐 Duolingo、Drops 等产品。

**问题**：这不是 Doramagic 的功能，但用户无法区分。如果推荐错误，用户会认为是 Doramagic 的问题。

## 需要重新思考的根本问题

1. **Doramagic 的目标用户是谁？** 开发者（"用 React 做 X"）还是普通用户（"我要英语学习工具"）？
2. **GitHub 搜索路径是否应该保留？** 如果保留，需要什么级别的改进？
3. **知识积木库如何扩展到终端用户场景？** 需要什么样的积木分类体系？
4. **LLM 依赖如何降低？** 当所有 LLM 服务都不可用时，Doramagic 能否仍然提供有价值的产出？
5. **Doramagic 作为 OpenClaw skill 的定位是什么？** 是"知识提取工具"还是"智能推荐助手"？

## 全局规范更新

本次会话中新增了以下全局规范：
1. **发布任务使用子代理**（~/.claude/CLAUDE.md 10.3 节）
2. **不编造原则**（memory 系统）

## 今日发布

| 版本 | 平台 | 状态 |
|------|------|------|
| v12.3.1 | GitHub + ClawHub | ✓ |
| v12.3.2 | GitHub + ClawHub | ✓ |
| v12.3.3 | GitHub + ClawHub | ✓ |
| v12.3.4 | 待测试通过后发布 | 待定 |

## 下一步

启动产品架构重新思考（/office-hours 或 /plan-ceo-review），回答上述 5 个根本问题。
