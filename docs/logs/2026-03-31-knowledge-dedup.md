# 知识库冗余清理
日期: 2026-03-31
执行者: Claude Code (sonnet)

## 做了什么

### 第一步：修复 56 个 brick_id 冲突

3 个 JSONL 文件中存在重复 brick_id（内容不同但 ID 相同）：

| 文件 | 冲突数 | 原因 | 修复方式 |
|------|--------|------|---------|
| `content_creation.jsonl` | 25 | l2-001～l2-025 第二批被分配了已有 ID | 重编号为 l2-173～l2-197 |
| `messaging_integration.jsonl` | 25 | l2-001～l2-025 第二批被分配了已有 ID | 重编号为 l2-107～l2-131 |
| `email_automation.jsonl` | 6 | l2-003～l2-008 第二批被分配了已有 ID | 重编号为 l2-026～l2-031 |

修复后所有知识内容保留（无丢失），ID 全局唯一。
已同步到原有的 4 份物理副本。

### 第二步：删除 knowledge/migrated/ 历史残留

- 删除了 `knowledge/migrated/` 目录（21 个 YAML + 1 个 JSONL，共 3.5 MB）
- 已确认无代码直接依赖该路径（唯一引用的 `doramagic_compiler.py` 已用 `if d.exists()` 守卫，删除后自动跳过）
- 更新了 `skills/doramagic/scripts/doramagic_compiler.py` 注释，移除 `migrated` 从导入循环

### 第三步：4 份变 1 份（架构简化）

**原状态**：4 份完全相同的物理副本
- `bricks/` (根目录，50 JSONL + 2 MD, ~14 MB)
- `knowledge/bricks/` (50 JSONL, ~13 MB)
- `skills/doramagic/bricks/` (50 JSONL, ~13 MB)
- `skills/doramagic/knowledge/bricks/` (50 JSONL, ~13 MB)

**新状态**：1 份物理副本 + 3 个符号链接
- `knowledge/bricks/` — 唯一物理副本（添加了 BRICK_INVENTORY.md、INDEX.md）
- `bricks/` → `knowledge/bricks`（相对路径符号链接）
- `skills/doramagic/bricks/` → `../../knowledge/bricks`（相对路径符号链接）
- `skills/doramagic/knowledge/bricks/` → `../../../knowledge/bricks`（相对路径符号链接）

**修改的文件**：
- `scripts/release/package_skill.sh`：更新注释说明知识源，packaging 时从 `knowledge/bricks/` 复制（通过 rsync knowledge/ 整体同步）
- `skills/doramagic/scripts/doramagic_compiler.py`：更新注释移除 migrated 引用
- `knowledge/INDEX.md`：更新目录结构说明，移除 migrated/，记录符号链接架构
- `CLAUDE.md`：更新 Bricks 知识积木一节，说明 `knowledge/bricks/` 为唯一物理源

## 关键决策

**为什么选择 knowledge/bricks/ 作为唯一物理源而非 bricks/ (根目录)?**
- `knowledge/INDEX.md` 已明确声明 `knowledge/` 是"已编译、已验证"的正式知识库
- 编译器 `doramagic_compiler.py` 的目录优先级就是 `knowledge/ > bricks_v2/ > bricks/`
- 根目录 `bricks/` 被标注为"V1 Legacy"，作为符号链接保留向后兼容更合理

**为什么根目录 bricks/ 保留为符号链接而不直接删除?**
- 多处代码做 `root / "bricks"` 路径回退（`flow_controller.py`、`runtime_paths.py`、`brick_injection.py`、测试文件）
- 符号链接让所有现有路径继续工作，无需修改任何代码
- 符号链接保留了 `BRICK_INVENTORY.md` 等文档文件的原始引用路径

**为什么 package_skill.sh 用 rsync knowledge/ 整体同步，而非只复制 bricks/?**
- 打包需要完整的 `knowledge/`（包含 api_catalog/、scenes/）
- rsync 方式与 `scripts/INDEX.md` 中已有的同步惯例一致（`rsync -av knowledge/ skills/doramagic/knowledge/`）

## 遇到的问题

1. 原始 Python 脚本查找 `id` 字段，实际字段名是 `brick_id` —— 直接在脚本中修正
2. 根目录 `bricks/` 有额外文件 `BRICK_INVENTORY.md`、`INDEX.md`，`knowledge/bricks/` 没有 —— 先复制过去再创建符号链接

## 踩坑记录

已追加到 `docs/pitfalls.md`：
- 4 份物理副本同步问题
- knowledge/migrated/ 不可再添加
- brick_id 修复必须同步所有副本

## 清理结果

| 项目 | Before | After |
|------|--------|-------|
| brick_id 冲突 | 56 个 | 0 个 |
| knowledge/migrated/ | 3.5 MB (22 文件) | 已删除 |
| 知识文件物理副本 | 4 份 (~54 MB) | 1 份 (~13 MB) |
| 节省磁盘空间 | — | ~44 MB |
| make check | — | 489 passed |

## 下一步

- 下次发布前运行 `package_skill.sh` 验证打包脚本正确从 `knowledge/` 读取
- 考虑在 CI 中加检查：`bricks/`、`skills/doramagic/bricks/` 必须是符号链接（防止未来误操作变回物理副本）
- `knowledge/INDEX.md` 中的 migrated/ 条目文字已清理，但 `docs/ARCHITECTURE.md` 和 `docs/PRODUCT_MANUAL.md` 还有旧引用，可在下次文档更新时一并清理（非阻断）
