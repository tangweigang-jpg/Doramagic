# 2026-04-24 · Category 重分类 + 多层 cache 混战 + CTO 误判后果

> 主干+part2 worklog：`2026-04-23-doramagic-ai-end-to-end-launch.md` / `2026-04-23-part2-install-modal-pivot.md`。
> 本轮紧接 part2，跨零点进入 2026-04-24。

## 触发

CEO 浏览 doramagic.ai 首页，发现 81 颗 crystal **全部挂着 "量化金融" 一个标签**。根因：我发布 71 颗时 SUPPLEMENTAL 里统一写死 `category_slug: "quant-finance"`，没有根据 skill 本质细分。保险 / 合规 / 会计 / 衍生品类被一刀切。

## 正确修复路径（DB 层）

新加 4 个 finance 细分 category + 将 8 颗 data-focus 移到已有 `data-engineering`，共 21 颗 UPDATE。

**Categories before（5）**：quant-finance / data-engineering / code-review / technical-writing / devops

**Categories after（9）**：
| category | crystals |
|---|---|
| quant-finance 量化金融 | 54 |
| data-engineering 数据工程 | 10（原 2 + 新 8） |
| insurance-actuarial 保险精算 🆕 | 2 |
| regtech-compliance 合规科技 🆕 | 2 |
| derivatives-pricing 衍生品定价 🆕 | 5 |
| accounting 会计记账 🆕 | 3 |
| code-review 代码审查 | 2 |
| technical-writing 技术写作 | 2 |
| devops · 运维自动化 | 3 |

SQL 脚本 `/tmp/recategorize.sql`，单 transaction 完成 INSERT + 5 组 UPDATE。

## 然后就开始地狱了

DB 改完后**首页永远只显示 2 个 category tabs**。我一路挖下来踩了 7 个坑，每一个都以为是最后一个。**事后列出来，便于未来任何 session 不再重蹈**：

### 坑 1 · ISR `revalidate = 3600` 假凶手
首页 `export const revalidate = 3600` 让我以为 1 小时 ISR cache 锁住了旧数据。改为 `export const dynamic = "force-dynamic"` 每请求 SSR。修完仍看到旧数据 → **不是根因**。

### 坑 2 · Next.js Full Route Cache 假凶手
`rm -rf /opt/doramagic-web/.next/cache` + pm2 restart 两台。仍旧。**不是根因**。

### 坑 3 · pm2 reload 不清 Next runtime 假凶手
`pm2 delete doramagic-web && pm2 start server.js`（nuclear restart）。仍旧。**不是根因**。

### 坑 4 · **Singapore Prisma client 是 sqlite 生成的真凶**
直接在 Singapore 跑 `node -e "prisma.category.findMany()"` → **Error code 14: Unable to open the database file**（SQLITE_CANTOPEN）。

根因：我之前用 `rsync .next/standalone/` 把**本地 build 产的 sqlite-Prisma-client** 覆盖到 Singapore（本地 CEO 用 sqlite dev，standalone bundle 自带 sqlite client）。绕过了 deploy.sh 里的 `npx prisma generate` 步骤。

### 坑 5 · **rsync `--delete` 误删 prisma/ 目录**
修坑 4 时我跑 `rsync -az --delete .next/standalone/ root@singapore:/opt/doramagic-web/` —— `--delete` 把 Singapore 的 `/opt/doramagic-web/prisma/` 整个删了（standalone bundle 不含 prisma/）。`npx prisma generate` 报 `prisma/schema.prisma: file not found`。

修法：`ssh london 'tar cf - -C /opt/doramagic-web prisma' | ssh singapore 'cd /opt/doramagic-web && tar xf -'` 从 London 恢复。

### 坑 6 · **Prisma CLI 被意外升到 7.8.0 breaking change**
Singapore 跑 `npx prisma generate` 报：
```
Error: The datasource property `url` is no longer supported in schema files.
Move connection URLs for Migrate to prisma.config.ts
```
Prisma 7.0 移除了 schema.prisma 里 `url = env("DATABASE_URL")` 语法。Singapore 装的是 7.8.0（npm 在某个 install 时抓了最新），London 是 6.19.3。

修法：`npx -y prisma@6.19.3 generate` 在 Singapore 强制用老版 CLI。

### 坑 7 · **Caddy reload 误报 + 真正的传输层 cache 谜团**
修完 Prisma 后：
- 两台 server **localhost:3000 直连 Next** → **6 categories** ✓
- 两台 server **localhost:443 经 Caddy** → 6 categories ✓（caddy reload 之后）
- 我本机 **curl 8.208.25.189 直连 origin IP** → **39 × 量化金融（旧）** ✗
- **doramagic.ai 经 Cloudflare** → 39 × 量化金融（旧）✗

我一度以为是 Caddy reverse_proxy 的隐性 cache，但 Caddyfile 只是纯 reverse_proxy，没 cache directive。`systemctl restart caddy` 也无改变。

**最终精准定位**：从 **London 内部 curl 其自身 public IP** → 返 6 ✓。从**我本机 curl 同一 IP** → 返 2 ✗。响应 header 完全一致（via Caddy / x-powered-by Next）。

结论：**不是 server 侧任何一层 cache**。是**跨境网络路径里某个中间层 cache**——CF Tiered Cache / APO / ISP 透明代理等。`cf-cache-status: DYNAMIC` 不足以排除所有 CF feature。

**未完成的最后动作**：CEO 去 CF dashboard 点 "Purge Everything" + 浏览器 Cmd+Shift+R。未验证。

## CTO 多次误判 post-mortem

本轮我**连续 4 次下判断都是错的**：

| # | 错误判断 | 真实情况 | 教训 |
|---|---|---|---|
| 1 | "首页 ISR cache 导致看旧数据" | 是 Prisma client 错 | 先验证数据层再假设渲染层 |
| 2 | "web/ 不在版本控制" | `web/app/.git` 早存在 + private repo 已配 | 跑 `ls -la` 前不要下"没 git" 结论 |
| 3 | "Caddy 有隐性 cache" | Caddy 透传，是 CF 传输层 | 只要 same-machine curl 行为不同，先怀疑 client-side diff |
| 4 | "Cloudflare 按 cf-cache-status: DYNAMIC 就是不 cache" | CF 有 APO/Tiered/Argo 多层，DYNAMIC 不够完整 | 多阅 CF 文档，不单看一个 header |

**共通教训**：**在 5 个假设都不验证的情况下批量做 nuclear 操作（`rm .next/cache`、`pm2 delete`、`rsync --delete`、`restart caddy`）只会放大 blast radius**。这次放大到 "prisma/ 目录被误删 + Prisma CLI 被升到 breaking version"。

下次：**先 smallest-possible 诊断（如 `node -e` 直查 Prisma）再动手**。

## 相关 commits

`tangweigang-jpg/doramagic-web`（private）:
- `860edff` product pivot + pipeline fixes (前 session)
- `62d7899` Browse all crystals tile
- `2f21ecd` code review H1 + H2 fixes

本轮 **DB 级改动不进 git**（属于 data migration，未来需要一个 migration 脚本文件归档）。

## 遗留清单

| # | 债务 |
|---|---|
| A | CF cache purge 未执行（UI 层等 CEO） |
| B | DB category migration 未入 prisma migration history |
| C | deploy.sh 的 `rsync -az --delete` 应 `--exclude=prisma` 避免踩坑 5 |
| D | Singapore Prisma CLI 应 pin 到 6.19.3 避免坑 6（`npm install --save-exact prisma@6.19.3`） |
| E | `revalidate` 从 3600 降到 force-dynamic（保留，已 commit `860edff` 系列） |
| F | 本地 sqlite schema.prisma vs 生产 postgres 的分裂长期债（之前 deploy.sh 的 sed 兜底仍在） |
| G | batch-v1 65 颗 FAQ/description 机器味（product quality 非紧急） |

## 最终验证（待 CEO CF purge 后）

```bash
curl -s "https://doramagic.ai/zh" | grep -oE "(保险精算|合规科技|衍生品定价|会计记账|量化金融|数据工程)" | sort -u | wc -l
# 期望：6
```

---

*2026-04-24 · Doramagic CTO 视角 · 跨零点增量*
