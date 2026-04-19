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
- ~~不要发布后不同步 skills/doramagic/packages/ 副本~~ 已解决：v13.1.0 起 Python 代码通过 pip 包分发，skill 目录不再包含 packages/ 副本（修复于 2026-04-01）
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
- 不要在 flow_controller.py 中用 Path(__file__).parents[N] 硬编码路径加载其他包的模块（因为 pip install 后 site-packages 布局与开发布局不同，parents[2] 会指向错误目录；应改用标准 import，发现于 2026-04-01）
- 不要在 hatchling 多包配置下使用 editable install（因为 hatchling 对多路径 packages 的 editable 模式支持有限，只有 wheel install 正常工作，发现于 2026-04-01）
- 不要把 doramagic_product.__init__ 中重量级 import 放在模块级（因为 pipeline.py 有断裂依赖 run_skill_compiler，会导致整个包 import 失败；应用 lazy import __getattr__ 模式，发现于 2026-04-01）
- 不要在 pip 包的 CLI 中无条件调用 os.fork()（因为 Windows 没有 fork，pip 包面向所有平台；应加 sys.platform 检查，发现于 2026-04-01 代码审查）

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

## OpenClaw Skill 平台约束（2026-04-02 专题发现）

- 不要在 SKILL.md body 中使用 `{baseDir}`（因为 OpenClaw 只在 hooks command 中替换该变量，body 中是字面量，会导致 read ENOENT，发现于 2026-04-02）
- 不要使用相对路径调用 read 工具（因为 OpenClaw read 相对路径基于 workspace 根目录而非 skill 目录，必须用绝对路径 `~/.openclaw/workspace/skills/dora/...`，发现于 2026-04-02）
- 不要在 SKILL.md 中引用 Grep 或 Glob 工具（因为 OpenClaw 原生工具只有 read/write/edit/exec，没有 Grep/Glob，发现于 2026-04-02）
- 不要把输出格式模板放在外部 scaffold 文件中（因为 Sonnet 只有 ~17% 概率读取外部 scaffold 文件，但 100% 读取 SKILL.md 本身；模板必须内嵌到 SKILL.md 中，发现于 2026-04-02）
- 不要要求 Sonnet 一次生成多个文件（因为每增加一个文件的 read+write 调用，跳步概率指数增长；4 文件方案成功率 ~17%，1 文件方案成功率 ~67%，发现于 2026-04-02）
- 不要要求用户修改 OpenClaw 配置来适配 skill（因为普通用户不会编辑 exec-approvals.json 或 openclaw.json，skill 必须在零配置下工作，发现于 2026-04-02）
- 不要用 `{placeholder}` 格式做占位符（因为会和 JSON/YAML 语法混淆且容易泄漏；用 `REPLACE_WITH_XXX` 格式，发现于 2026-04-02）
- 不要让 Sonnet 用 exec mkdir 创建目录（因为 exec 需要审批；write 工具会自动创建目录，发现于 2026-04-02）
- 不要让 brick summary 只包含 failure/constraint（因为 71% 的砖块知识（pattern/rationale/capability）被丢弃，导致生成内容只有"不要做什么"没有"怎么做"；summary 必须包含 PATTERNS 和 RATIONALE 节，发现于 2026-04-02）

## 管线代码（2026-04-09 专题发现）

- 不要用手写 prompt 绕过管线代码派子代理执行 SOP（因为手写 prompt 太笼统，子代理在有限 context 内自行裁量跳步——Step 2.4 被 100% 跳过，产出尺寸只有标杆的 50%；管线代码有步骤强制、prompt 模板、状态持久化，必须用 `make sop-run-*` 驱动，发现于 2026-04-09）
- 不要给 Pydantic `use_enum_values=True` 的 model 用 `.value` 访问 enum 字段（因为 Pydantic 在构造时已将 enum 转为 str，运行时 `.value` 会 AttributeError；用字符串字面量比较 `c.constraint_kind == "claim_boundary"`，发现于 2026-04-09）
- 不要给 Pydantic model 传入未在 schema 中声明的字段（因为 Pydantic v2 默认 `extra="ignore"` 会静默丢弃未知字段，不报错但数据丢失；必须先在 schema 类中声明字段，再在管线代码中使用，发现于 2026-04-09）
- 不要假设蓝图 YAML 中 business_decisions 的 key 名（因为实际是 `decision`/`rationale`/`stage`/`evidence`，不是 `content`/`description`/`reason`；编译器读取蓝图数据时先 grep 一个实际 YAML 确认字段名，发现于 2026-04-09）
- 不要把 validation_threshold 的 DSL 格式（`condition → FAIL`）直接放入 `assert` 语句（因为 `→ FAIL` 不是合法 Python，会 SyntaxError；检测 `→`/`->` 时转为注释，仅纯 Python 表达式用 assert，发现于 2026-04-09）
- 不要开发管线代码而不建版本文档（因为管线代码从 v0.1.0 到需要修复时没有 CHANGELOG、没有 pyproject.toml，无法追踪哪些 SOP 步骤已实现、哪些有 bug；每个管线包必须有 CHANGELOG.md + pyproject.toml，发现于 2026-04-09）
- 不要给 `ConstraintStore` 传入含 `domains/` 的路径（因为 `ConstraintStore.__init__` 自动拼 `self.base_path / "domains"`，传 `knowledge/constraints/domains` 会变成 `domains/domains`；传 `knowledge/constraints` 即可，发现于 2026-04-09）
- 不要把增量约束只存到 `_drafts/` 目录（因为晶体编译器从主 `finance.jsonl` 读取约束，_drafts 不在读取路径内；增量约束必须同时追加到主 JSONL + 备份到 _drafts，发现于 2026-04-09）
- 不要在蓝图 merge 后、晶体编译前忘记写回磁盘（因为 `load_blueprint()` 从磁盘读取，内存中的 merge 结果不会被编译器看到；修改蓝图后立即 write_text 回文件，发现于 2026-04-09）
- 不要用 `open(path, "w")` 原地覆盖重要 JSONL 文件（因为进程中断会导致数据截断；用 `tempfile` + `os.replace()` 原子写入，发现于 2026-04-09）

## Agent 架构（2026-04-13 专题发现）

### P-01: MiniMax Thinking Mode + Instructor tool_choice 冲突（2026-04-13）

**现象**：`run_structured_call` L1 Instructor 调用对 MiniMax 间歇性失败，错误为 `List should have at least 1 item after validation, not 0`。但模型实际产出了正确的 JSON。

**根因**：MiniMax 的 thinking mode 返回 `[ThinkingBlock, TextBlock]`。TextBlock 中包含完美的 JSON，但 Instructor 只解析 `ToolUseBlock`。找不到 tool_use block → 空列表 → validation 失败。

**解决方案**：新增 L1.5 层 — L1 失败后，先从 `l1_exc.last_completion` 中提取 JSON 并 validate，成功则直接返回。避免不必要的 L2 重新调用。

**教训**：Thinking mode 改变响应的 content block 结构。任何依赖 tool_use 强制输出的库（Instructor、LangChain structured output）在 thinking mode 下都可能失效。

### P-02: OpenAI 兼容 API 的 base_url 必须含 /v1（2026-04-13）

**现象**：`_raw_openai_call` 返回 `JSONDecodeError: Expecting value: line 1 column 1`。

**根因**：代码拼接 `url = f"{base_url}/chat/completions"`。如果 base_url 不含 `/v1`，实际请求 URL 是 `https://api.xxx.cc/chat/completions`，打到 HTML 页面而非 API 端点。API 返回 200 + HTML body → JSON 解析失败。

**解决方案**：CLI 文档注明 `--base-url` 必须包含 `/v1` 后缀。代码层面可考虑自动检测并追加。

### P-03: GPT 系列模型不适合多轮 agentic tool_use（2026-04-13）

**现象**：用 gpt-5.3-codex 和 gpt-5.4 跑 worker phase，全部 1-3 轮就结束（MiniMax 跑 10-26 轮）。产出极度浅薄。

**根因**：GPT 系列倾向于"直接回答"而非"迭代探索"。给它 tool 它也只调用 1 次就认为够了，不会像 MiniMax 那样主动多轮 read_file + grep_codebase 探索代码。

**解决方案**：Agent 设计需要适配不同模型的 agentic 行为。可能的方案：(1) 在 prompt 中强制要求最少 N 轮探索；(2) 在 agent loop 中检测"过早结束"并追加 follow-up message；(3) 对 GPT 系列使用不同的 max_iterations 和 prompt 策略。

### P-04: Step 3 merge 重建 missing_gaps 导致 BQ-04 失败（2026-04-13）

**现象**：Step 1 产出 7 个 missing gaps，但最终 blueprint 中 missing_gaps=0，BQ-04 FAIL。

**根因**：Step 3 merge 代码 `merged_missing = [d for d in merged_decisions if d.status == "missing"]` 从 decisions 重建 missing_gaps。但 LLM 的 BDExtractionResult 中，missing_gaps 列表和 decisions 列表是独立的，decisions 中可能没有设置 status="missing"。重建后列表为空。

**解决方案**：保留 step2_final.missing_gaps，不从 decisions 重建。Step 3 的新 missing BD 通过 status 过滤追加。

### P-05: 529 被 Instructor 截获导致无效降级（2026-04-13）

**现象**：MiniMax 529 过载时，agent 直接降级到 L2/L3，即使 L2/L3 一样会 529。

**根因**：Instructor 库的内部 retry 先截获 529，快速重试 3 次（无退避），全部失败后抛 InstructorRetryException。agent 将其视为 "schema 错误" 降级到 L2。传输层的指数退避从未执行。

**解决方案**：在 L1/L2 调用外包裹传输层重试循环（_TRANSPORT_RETRY_DELAYS = 5/10/20/40s），用 _is_transport_error() 判断是否为传输错误。传输错误 → 同级等待重试，不降级。Schema 错误 → 正常降级。

### P-06: 晶体字段作用域错位——改错字段还以为 host 忽略（2026-04-19）

**现象**：Session 27 v5.2 Fix A 动态化了 `skill_crystallization.skill_file_schema`（name/intent_keywords/fatal_guards），期望 OpenClaw 安装 Notice 从通用 "ZVT v5.2 Skill" 改为 UC 专属 "Actor Data Recorder"。文件层部署字节级一致，但 08:46 实测 Notice 文案完全没变。

**根因**：`skill_crystallization.skill_file_schema` 是**给 host 做 skill 路由匹配**的元数据（intent_keywords 决定 "say X to invoke" 命中），**Notice 渲染源是 `post_install_notice.message_template`**——两个字段作用域独立，改前者不影响后者。类似于 Session 27 前半段 v6.0 Runtime 弯路：把 "host 没按预期表现" 第一归因到 "host 忽略声明"，而不是 "我改错了字段"。

**解决方案**：
1. 要让 Notice 反映 UC 专属定位，改 `post_install_notice.message_template.positioning` 或新增 `skill_identity` 段（从 featured_use_cases 派生）
2. 编译脚本写入晶体字段时，为每个字段标注**消费者**（host-routing / Notice-render / skill-emit / user-facing-translate），作用域清晰
3. 行为未变时的排查顺序：先查字段作用域（该字段的消费者是谁？）→ 再查 host 解读能力

**关联 memory**：`feedback_crystal_host_relationship.md`（晶体被宿主解读而非字面执行）
