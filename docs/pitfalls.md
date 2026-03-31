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
- 不要在 Sonnet 子代理并行修改文件后切换 git 分支（因为未提交的改动会丢失，应先 commit 或 stash 所有代理产出，发现于 2026-03-29）
- 不要让 sys.path.insert 清理工具删除 `if` 守卫而不删除整个代码块（因为会留下空 `if` 导致 SyntaxError，发现于 2026-03-29）

## 发布

- 不要在 GitHub 发布版本中包含 research/、experiments/、races/ 等内部目录（因为会泄露内部信息，必须通过 publish_to_github.sh 清理，发现于 2026-03-25）
- 不要跳过发布预检直接 push（因为可能遗漏社区标准文件或包含内部文件，发现于 2026-03-25）
- 不要只推 git tag 而不创建 GitHub Release（因为用户在 Releases 页面看不到版本信息，发现于 2026-03-29）
- 不要用中文写 GitHub 上的 commit message 和文档（因为 GitHub 是面向国际社区的正式发布仓库，规范要求英文，发现于 2026-03-29）
- 不要发布时只更新 pyproject.toml 版本号（因为 SKILL.md、README.md、marketplace.json 也有版本号，不同步会导致用户困惑，发现于 2026-03-29）
- 不要发布后不同步 skills/doramagic/packages/ 副本（因为 skill 运行时用的是副本不是主包，副本落后等于用户装了旧代码，发现于 2026-03-29）
- 不要让 publish_preflight.sh 和 publish_to_github.sh 的排除列表不同步（因为预检会误报，或发布会遗漏清理，发现于 2026-03-29）
- 不要忘记发布到 ClawHub（因为 GitHub push 不等于 ClawHub 更新，用户通过 clawhub install 拿到的是 ClawHub 版本，发现于 2026-03-29）
- 不要只发布到一个 ClawHub slug（因为历史原因 "dora" 和 "doramagic" 两个 slug 都有用户安装，必须双发布，发现于 2026-03-29）

## 安全

- 不要让 LLM 调用无预算上限（因为 unbounded API 调用会导致成本失控，发现于 2026-03-25 CSO 审计）
- 不要在 stage15 fallback 中使用 LLM 控制的 regex 而不限长度（因为 ReDoS 漏洞，需加 200 字符限制，发现于 2026-03-25 CSO 审计）
- 不要跳过 DSD 和 confidence_system 的安全测试（因为安全回归会无法检测，发现于 2026-03-25 CSO 审计）

## 测试

- 不要用 `sys.path.insert` 拼接硬路径来跑测试（因为新环境容易配置失败，应迁移到 editable install，发现于 2026-03-28 项目分析）

## 环境

- 不要在 uv 创建的 venv 中用系统 pip 装包（因为 uv 和 pip 的包索引不一致，装了也找不到；必须用 `uv pip install`，发现于 2026-03-29）
- 不要让 pre-commit 的工具版本落后于 .venv 的工具版本（因为 pre-commit 会拒绝 .venv 能通过的代码，如 ruff 0.8 不认识 RUF059 规则，发现于 2026-03-29）

## 流程

- 不要跳过赛马直接独做核心功能（因为自己审自己有盲点，Codex 交叉审查发现了 7 个真实问题包括 3 个 HIGH 级，发现于 2026-03-29）
- 不要在计划中加入不影响目标的步骤（因为是伪工作，"删掉这步目标会受影响吗？"如果不会就不该存在，发现于 2026-03-29）
- 不要按技术排行榜选产品方向（因为应该从市场需求反推，ClawHub 下载数据比框架热度排行更能反映真实需求，发现于 2026-03-29）

## 打包与部署

- 不要在 setup_packages_path 的开发者布局检测中只判断 packages/ 和 skills/doramagic/ 是否存在（因为 ~/.openclaw/ 会同时含有旧版残留，应额外验证 pyproject.toml 或 Makefile 才算真正的开发目录，发现于 2026-03-29）
- 不要在 _brick_catalog_dir 中把 skills/doramagic/bricks/ 路径排在 bricks/ 之前（因为安装模式下 skills/doramagic/ 不存在，会解析到错误路径；应优先检查 DORAMAGIC_BRICKS_DIR 环境变量，发现于 2026-03-29）
- 不要在相关性过滤器中只用英文关键词匹配（因为 GitHub 返回的中文描述仓库会被误过滤；非 ASCII 字符占比高时应直接放行，信任 GitHub 搜索排序，发现于 2026-03-29）

## 知识库结构

- 不要把 bricks/、knowledge/bricks/、skills/doramagic/bricks/、skills/doramagic/knowledge/bricks/ 维护为独立物理副本（因为 4 份副本保证同步极难，brick_id 冲突修复后必须手动同步4次；正确做法是 knowledge/bricks/ 作为唯一物理副本，其余用符号链接，发现于 2026-03-31）
- 不要往 knowledge/migrated/ 添加新知识（因为该目录是旧格式历史残留，已被 knowledge/bricks/ 覆盖，已于 2026-03-31 删除）
- 修复 brick_id 冲突时不要只改一份副本（因为同一 JSONL 有 4 处物理副本，只改一处会在下次发布时被旧版覆盖，发现于 2026-03-31）
- 不要在版本字符串中硬编码版本号（因为发版后容易忘记同步，应从 SKILL.md 或 pyproject.toml 动态读取，发现于 2026-03-29）

## 通用

- 不要假设两个环境的 schema 一致（因为 legacy 生产表可能缺列，需做列探测/降级分支，来自 WhisperX 教训 2026-03-17）
- 不要把多个不同类型的问题混在一起修（因为容易混改出新 bug，来自 WhisperX 教训 2026-03-24）
- 不要依赖 LLM agent 执行多步异步操作（因为 MiniMax 等模型不遵守 SKILL.md 的轮询指令，脚本必须自己处理等待和输出，发现于 2026-03-30）
- 不要在 os.fork() 后依赖 stdout 回传结果（因为子进程关闭 stdout 后不可恢复，必须用文件中转如 output.json，发现于 2026-03-30）
- 不要设过低的苏格拉底追问阈值（因为 NeedProfileBuilder 对模糊需求过于自信，0.7 阈值导致大量应追问的需求被跳过，发现于 2026-03-30）
- 不要只看版本号就认为部署正确（因为 ClawHub 安装的 v12.4.1 实际内容是旧版 Soul Extractor，必须验证 SKILL.md 内容和脚本列表，发现于 2026-03-30）
- 不要在 skill 目录旁创建 .bak 备份（因为 OpenClaw 可能加载备份目录替代正式目录，导致运行旧代码，发现于 2026-03-30）
- 不要假设弱模型能执行复杂 SKILL.md 路由（因为 MiniMax-M2.7 完全无法理解编译/提取模式分支，每次都走错路径，Sonnet 一次成功，发现于 2026-03-30）
- 不要把多个模式塞进一个 SKILL.md（因为宿主 LLM 会跳过中间步骤直接走最"有趣"的路径，2026-03-31 测试证明 230 行 SKILL.md 导致积木匹配被完全绕过；拆分为单职责技能后每个技能只做一件事，发现于 2026-03-31）
- 不要在 OpenClaw 技能中依赖 hooks 机制（因为 hooks 是 Claude Code 的能力，OpenClaw 不支持技能级 hooks，只有提示词注入是可用的，发现于 2026-03-31）
- 不要把整理文档时移动的文件路径忘记同步到测试（因为 racekit 测试引用了 docs/dev-plan-codex-module-specs.md 的硬编码路径，文件移到 archive 后测试失败，发现于 2026-03-31）
