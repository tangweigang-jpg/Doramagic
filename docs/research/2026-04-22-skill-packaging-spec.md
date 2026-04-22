# Doramagic Skill 打包规范（ClawHub + GitHub Anthropic Skills 双通道）

**日期**：2026-04-22
**研究员**：opus subagent
**纪律**：严禁瞎编，每条结论标 **已查证** / **推测** / **不确定**

---

## 好消息：发布工具链已存在

Doramagic 内部有 `scripts/release/publish_to_github.sh` + `package_skill.sh`，已成功发布 doramagic 13 版本。**bp-009 打包不需要从零做**，只要把规范对齐、产出目录，走已有脚本即可。

---

## Part 1: ClawHub 规范要点

### 最小必需结构
```
{slug}/
├── SKILL.md       # 必需
└── LICENSE        # GitHub 通道硬性要求（ClawHub 侧推荐）
```
`scripts/` `references/` 可选。`_meta.json` **不要手写**——`npx clawhub@latest publish` 自动生成。`platform_rules.json` 不需要（除非 bp-009 要定制工具面限制）。

### SKILL.md frontmatter（已查证来源：docs.openclaw.ai/tools/creating-skills.md）
| 字段 | 必需 | 备注 |
|---|---|---|
| `name` | ✓ | slug 格式 `[a-z0-9-]` |
| `description` | ✓ | ≤1024 char |
| `license` | - | MIT/MIT-0 |
| `metadata.openclaw.emoji` | - | 单 emoji，推测 |
| `metadata.openclaw.skillKey` | - | 一般 = name |
| `metadata.openclaw.install[]` | - | `kind: brew/node/go/uv/download` |
| `metadata.openclaw.requires` | - | bins/env/config 依赖声明 |
| `metadata.openclaw.category` | - | **不确定**：doramagic 用了但官方未列 |

### 发布命令（已查证来自 publish_to_github.sh）
```bash
npx clawhub@latest publish <skill-dir> \
  --slug <slug> \
  --name "<Display Name>" \
  --version <semver> \
  --changelog "..." \
  --tags latest
```
发布后"几分钟安全扫描期"内 skill 不可见。

---

## Part 2: GitHub Anthropic Agent Skills 规范

### 必需字段（已查证来源：agentskills.io/specification）
| 字段 | 约束 |
|---|---|
| `name` | 1-64 char，`[a-z0-9-]`，**必须匹配父目录名** |
| `description` | 1-1024 char，前置触发关键词 |

### Progressive Disclosure 规则
- SKILL.md body 推荐 ≤5000 tokens（Claude Code 官方建议 ≤500 行，本地样本 80-180 行最常见）
- `scripts/` `references/` `assets/` 按需加载
- 超长内容切到 `references/*.md`

### Plugin Marketplace 分发（走 `/plugin marketplace add <org/repo>`）
repo 需要额外外包一层：
```
<repo>/
├── .claude-plugin/marketplace.json
└── plugins/<plugin-name>/
    ├── .claude-plugin/plugin.json
    └── skills/<skill-name>/SKILL.md
```

---

## Part 3: 双兼容方案

### 最小兼容 frontmatter
```yaml
---
name: finance-bp-009-zvt           # 严格匹配目录名
description: >
  <前置关键词触发，≤1024 char>
license: MIT
metadata:
  openclaw:
    emoji: "📈"
    skillKey: finance-bp-009-zvt
---
```

### 冲突处理
- `metadata` 嵌套 vs spec 要求 string→string：**实测 Claude Code 不校验，保留 openclaw 嵌套无害**
- `_meta.json` 在 GitHub 分发时被 Claude Code 忽略无害
- 一份 SKILL.md 双通道通用

---

## Part 4: bp-009 skill 包草案

### 目录结构（结构参考 `a-stock-macd-backtest`）
```
finance-bp-009-zvt/
├── SKILL.md                       # 80-150 行
├── LICENSE                        # MIT
├── references/
│   ├── seed.yaml                  # 复制自 knowledge/sources/finance/finance-bp-009--zvt/LATEST.yaml
│   └── bp-009-knowledge.md        # 切片: Hard Gates + domain_constraints + anti_patterns
└── scripts/                       # 可选，如有可执行脚本
```

### SKILL.md body 结构
```
## 触发判断          # 与其他 finance skill 的边界
## 执行流程          # stage_id 映射
## 关键规格锁        # Hard Gates 表（从 seed.yaml 切片）
## 已知框架缺口      # domain_constraints FAILURE 类条目
## 禁止事项          # anti_patterns 列表
## 参考文件          # 指向 references/seed.yaml + bp-009-knowledge.md
```

### 文件来源表
| 文件 | 来源 | 必需 |
|---|---|---|
| `SKILL.md` | 新写（按上面结构从 seed.yaml 摘录） | ✓ |
| `LICENSE` | 项目 LICENSE 或新建 MIT | ✓ |
| `references/seed.yaml` | 复制自 `knowledge/sources/finance/finance-bp-009--zvt/LATEST.yaml` | ✓ |
| `references/bp-009-knowledge.md` | 从 seed.yaml 三大 section 切片 | ✓ |
| `scripts/` | 按需 | - |
| `_meta.json` | 发布时自动生成 | 不手写 |
| `platform_rules.json` | 不需要 | - |

---

## 未解点（明示标注）

1. **ClawHub 体积上限**：未查到
2. **`metadata.openclaw.category` 是否合法**：doramagic 使用但 docs 未列
3. **`emoji` 必须单字符 vs 字符串**：推测单字符（唯一样本 `"🪄"`）
4. **CLI 名称分歧**：docs 说 `clawhub skill publish`，脚本用 `npx clawhub@latest publish`。**以脚本为准**（已成功发布 13 次）
5. **`_meta.json` 官方 schema**：推测（ownerId/slug/version/publishedAt，三样本一致）

---

## Sources

### WebFetch
- `https://openclaw.ai/` + `https://docs.openclaw.ai/*`
- `https://agentskills.io/` + `https://agentskills.io/specification`
- `https://code.claude.com/docs/en/skills` + `https://code.claude.com/docs/en/plugin-marketplaces`
- `https://github.com/anthropics/skills`

### 本地一手样本
- `~/.openclaw/workspace/skills/doramagic/` (SKILL.md, _meta.json, platform_rules.json)
- `~/.openclaw/workspace/skills/{zvt-quant, a-stock-macd-backtest, backtest-expert, business-plan, baoyu-slide-deck}/`
- `scripts/release/{README.md, package_skill.sh, publish_to_github.sh}`
