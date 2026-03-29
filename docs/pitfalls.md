# 踩坑记录

> 开发前必读。每次遇到问题后追加到对应分类下。
> 格式: 不要<做法>（因为<原因>，发现于<日期>）

---

## 架构

- 不要把整个产品当一次性检索脚本，缺少"先理解需求、再组织工作、最后逐步交付"的代理工作流（因为 singleshot.py 的根本缺陷，发现于 2026-03-25）
- 不要串行执行 ClawHub/Local/GitHub 搜索（因为 GitHub 占 97% 耗时会拖垮整体体验，应改为并发，发现于 2026-03-25）

## 工具链

- 不要用 `codex exec -q "prompt"` 调用 Codex CLI（因为 `-q` 不是 exec 子命令的参数，prompt 应作为位置参数传入，发现于 2026-03-29）
- 不要用 Python 脚本批量替换文件内容后直接 git add 而不验证文件完整性（因为可能意外清空文件并提交空文件到 git，发现于 2026-03-29）
- 不要让 Codex 和 Claude Code 在同一个 git 工作目录赛马（因为 Codex sandbox 无法操作 .git/，两边改动会互相覆盖；必须用独立 git clone 隔离，发现于 2026-03-29）
- 不要在 pyproject.toml 的 extend-per-file-ignores 中重复同一个文件键（因为 TOML 不允许 duplicate key，会导致 ruff 解析失败，发现于 2026-03-29）

## 发布

- 不要在 GitHub 发布版本中包含 research/、experiments/、races/ 等内部目录（因为会泄露内部信息，必须通过 publish_to_github.sh 清理，发现于 2026-03-25）
- 不要跳过发布预检直接 push（因为可能遗漏社区标准文件或包含内部文件，发现于 2026-03-25）

## 安全

- 不要让 LLM 调用无预算上限（因为 unbounded API 调用会导致成本失控，发现于 2026-03-25 CSO 审计）
- 不要在 stage15 fallback 中使用 LLM 控制的 regex 而不限长度（因为 ReDoS 漏洞，需加 200 字符限制，发现于 2026-03-25 CSO 审计）
- 不要跳过 DSD 和 confidence_system 的安全测试（因为安全回归会无法检测，发现于 2026-03-25 CSO 审计）

## 测试

- 不要用 `sys.path.insert` 拼接硬路径来跑测试（因为新环境容易配置失败，应迁移到 editable install，发现于 2026-03-28 项目分析）

## 通用

- 不要假设两个环境的 schema 一致（因为 legacy 生产表可能缺列，需做列探测/降级分支，来自 WhisperX 教训 2026-03-17）
- 不要把多个不同类型的问题混在一起修（因为容易混改出新 bug，来自 WhisperX 教训 2026-03-24）
