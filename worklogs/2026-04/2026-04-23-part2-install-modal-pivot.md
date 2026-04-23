# 2026-04-23 (part 2) · "下载晶体" 改造 · URL Modal + i18n + analytics route

> 同日增量日志。主干日志：`2026-04-23-doramagic-ai-end-to-end-launch.md`（71 颗 crystal 上线 + 端到端 pipeline 跑通）。

## 触发

CEO 在主干日志完成后追问三连：

1. "现在点击下载晶体，用户得到一个什么结果？"
2. "我告诉过你了，原来是下载一个晶体，现在是用户获取到 url 了"
3. "下载晶体已经改版成为用户获取到 url 了吗？所有的晶体都是如此吗？"

第 2 条揭示 **我忘了 CEO 在本 session 第一条消息里就明确的产品意图**："用户不再是获得一颗晶体，而是转而获得两种 url（ClawHub + GitHub）"。主干日志里我做了 API/publish 管线，但**前端"下载晶体"按钮仍然是旧的 .seed.md 下载**，产品行为和意图脱节。

## 修复

### 前端：CrystalSidebar Modal（src/components/crystal/CrystalSidebar.tsx）

按钮 "下载晶体" 行为改造：
- **改前**：requireAuth → fetch `/api/crystals/[slug]/download` → blob → 触发浏览器下载 `{slug}.seed.md`（500KB YAML 文件）
- **改后**：requireAuth → 打开 Modal（URL 聚合 + 一键复制）+ fire-and-forget POST 到 `/download` 保留 `downloadCount` 指标

Modal 展示 4 种获取方式（参考同花顺 SkillHub 模式）：

| 区块 | 内容 |
|---|---|
| Agent 用户 | 可复制 prompt，指导 host AI（Claude / Cursor / OpenClaw / ChatGPT）从 ClawHub 或 GitHub 读取 SKILL.md 并应用 |
| CLI 用户 | `npx clawhub@latest install {slug}` 一键命令 |
| ClawHub 页面 | `https://clawhub.ai/tangweigang-jpg/{slug}` 可点击链接 |
| GitHub 源 | `https://github.com/tangweigang-jpg/doramagic-skills/tree/main/skills/{slug}` 可点击链接 |

每行都有复制按钮 + 复制成功反馈（"已复制 ✓" 1.5s 后回退）。

### 后端：/api/crystals/[slug]/download route 瘦身

- **改前**：read `crystal.seedContent`（~500KB）+ `{{var}}` 模板替换 + 返回 markdown blob + ETag cache
- **改后**：pure analytics — 只 insert Download 行 + increment `Crystal.downloadCount`，返 `{ok:true}` JSON
- 原因：前端不再需要 seed 内容（用户自己从 ClawHub/GitHub 获取），旧行为只是浪费 DB 带宽 + 维护攻击面

### i18n

`messages/{zh,en}/crystal.json` 新增 `install.*` 命名空间 10 keys：
- `title` / `subtitle` / `sectionAgent` / `sectionCli` / `sectionClawhub` / `sectionGithub`
- `copy` / `copied` / `close` / `footer`
- `agentPromptTpl`（含 `{slug}` / `{clawhubUrl}` / `{githubUrl}` 占位符）

中文页展示"安装此晶体"，英文页展示 "Install this crystal"。验证方式：`curl /zh/crystal/a-stock-quant-lab | grep 安装此晶体` vs `/en/crystal/a-stock-quant-lab | grep "Install this crystal"`。

## 覆盖范围验证

抽样 5 颗跨质量层的 crystal，每颗详情页 HTML 都含 "安装此晶体" Modal：
- qlib-ai-quant（locked）
- insurance-loss-reserving（locked）
- macro-economic-model（batch-v1，late-add）
- freqtrade-crypto-bot（batch-v1）
- zipline-daily-backtest（batch-v1）

**全部 81 PUBLISHED crystals** 统一应用新 Modal（`CrystalSidebar.tsx` 是共享组件）。未来新发布 crystal 也自动继承。

## CTO 误判记录

主干日志把"web/ 不在版本控制"列为技术债之一，并给出 A/B/C 三方案让 CEO 决定。CEO 反问 "最佳解决方案是什么" —— 逼我替他做判断（不推卸）。我推荐 A (独立 private repo)。

**动手时才发现**：`web/app/.git` **早就存在**，remote 已配 `github.com/tangweigang-jpg/doramagic-web` (PRIVATE)。CEO 的架构一直是对的，我完全没先跑 `ls -la` / `git remote -v` 就下结论。

- **教训**：摸底先于论证。即使判断方向对，过程中没做基础 verification 会让 CEO 对整体结论置信度下降。
- **意外收获**：今天 7 处 web/ 改动（eslint.config / deploy.sh / publish route / download route / CrystalSidebar / messages × 2）现在**一次性 commit** 到对的 repo，弥补了本 session 期间多次只靠 rsync 部署、无 git 历史的断层。

## 交付

| 改动 | 位置 |
|---|---|
| Commit `860edff` | `tangweigang-jpg/doramagic-web` (PRIVATE) main 分支，pushed |
| 文件变更 | 7 files, 265 insertions, 180 deletions |
| 覆盖 i18n | zh + en（`install.*` 10 keys） |
| 部署 | London + Singapore 两台 PM2 reload |
| 产线状态 | 81 crystals 全部应用新 Modal，首页 / 详情页 HTTP 200 |

## 累计当日成果（主干 + 本增量）

| 渠道 | 状态 |
|---|---|
| ClawHub | 71 颗 skill 上线 + suspicious 清除 |
| GitHub `doramagic-skills` (public) | surgical patch 71 skills + rename 1 slug + 5 locked bilingual 注入 + 65 batch-v1 bilingual 注入（4 commits pushed） |
| GitHub `Doramagic` (public) | 10 commits pushed（emit_skill_bundle / naming_map / skill_metadata / batch_generate_metadata / batch_publish_auto / publish_to_doramagic / worklog × 2） |
| GitHub `doramagic-web` (PRIVATE) | 1 commit pushed（7 files：eslint / deploy.sh / 2 API routes / CrystalSidebar / i18n × 2） |
| Doramagic.ai 首页 | 0 Crystals → **81 PUBLISHED Crystals** + 4836 constraints |
| 用户下载体验 | 下载 `.seed.md` → **URL Modal 一键复制安装指令**，81 颗统一 |

## 剩余债务（各自单独轮次）

- T15 Discussion/CrystalRequest schema drift → 正规 prisma migration
- T17 2 颗空白 skill（life-insurance-math / riskfolio-optimization）需先跑 extraction 产 seed
- batch-v1 65 颗 FAQ / definition 机器味 → 精品化升级
- Cloudflare Authorization header 剥离根治（目前用 X-Publish-Key fallback）
- Prisma CLI 版本不一致（London 6.19.3 / Singapore 7.8.0）
- schema.prisma sqlite/postgres dev-prod 长期分裂（deploy.sh sed 兜底中）

---

*增量日志由 Doramagic CTO 视角撰写 · 2026-04-23 · 同日晚间*
