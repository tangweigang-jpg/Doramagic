# 4 个打包与运行时问题修复
日期: 2026-03-30
执行者: Claude Code (Sonnet 4.6)

## 做了什么

修复了 4 个子代理报告的问题，每个独立提交：

### 问题 1：版本号硬编码（低优先级）
- 文件：`skills/doramagic/scripts/doramagic_main.py`
- 修复：新增 `_get_version()` 函数，先读 `SKILL.md` 的 `version:` 字段，回退时读 `pyproject.toml`
- `_build_rich_message` 中的 footer 从硬编码 `v12.1.2` 改为 `v{_get_version()}`

### 问题 2：setup_packages_path 误判开发者模式（高优先级）
- 文件：`skills/doramagic/scripts/doramagic_main.py`
- 问题：`~/.openclaw/` 同时含有旧版 `packages/` 和 `skills/doramagic/` 时被误判为开发者布局
- 修复：增加 `pyproject.toml` 或 `Makefile` 存在检查，两者都不存在则回退到 self-contained 模式

### 问题 3：_brick_catalog_dir 路径解析问题（高优先级）
- 文件：`packages/controller/doramagic_controller/flow_controller.py`（+skills 副本同步）
- 问题：候选路径顺序不对，未利用 `DORAMAGIC_BRICKS_DIR` 环境变量
- 修复：
  1. 优先读取 `DORAMAGIC_BRICKS_DIR` 环境变量（setup_packages_path 已正确设置）
  2. 候选路径顺序改为：先 `root/bricks/`（self-contained），再 `root/skills/doramagic/bricks/`（dev）
- 注：package_skill.sh 中 bricks/ 打包步骤已存在，无需修改

### 问题 4：相关性过滤器只做英文匹配（中优先级）
- 文件：`packages/executors/doramagic_executors/discovery_runner.py`（+skills 副本同步）
- 问题：GitHub 返回中文描述的仓库，英文关键词无法匹配，被误过滤
- 修复：
  1. 提取纯 ASCII 关键词用于匹配（过滤掉可能混入的中文关键词）
  2. 当 searchable 文本非 ASCII 字符占比 > 30% 时，直接放行（信任 GitHub 搜索排序）

## 关键决策

- 问题 4 的方案选择：放行 vs LLM 语义判断。选择放行是因为 GitHub 搜索已做相关性排序，
  额外引入 LLM 判断会增加成本和延迟，且 fallback 模式下 LLM 不可用。
- 问题 3：_brick_catalog_dir 未使用 DORAMAGIC_BRICKS_DIR 是设计缺陷，两个函数应该保持一致。
  最简单修复是让 _brick_catalog_dir 也读 env var，而不是重写路径解析逻辑。

## 遇到的问题

- `make test` 在 background 模式下输出为空（工具问题），改用直接指定 PYTHONPATH 运行 pytest

## 踩坑记录

更新到 docs/pitfalls.md（新增"打包与部署"分类，4 条记录）

## 下一步

- 可考虑为 discovery_runner 增加测试覆盖中文描述场景
- _brick_catalog_dir 的测试目前没有覆盖已安装环境路径
