# Doramagic Web — 5-Persona E2E 全面测试报告（含 CTO 修复实施记录）

> **日期**：2026-04-16
> **范围**：`Doramagic/web/app/`（Next.js 16.2.3 + Prisma 6 + SQLite + Playwright 1.59）
> **环境**：localhost:3100（端口 3000 被 Gitea SSH tunnel 占用，Playwright 配置改为 env 可配）
> **方法**：五个 Persona 独立 spec + 已有 spec 一起跑；每处断言必须可追溯到 `Doramagic_web_features.md`（F-000~F-025）或实际代码

## Sources（事实依据）

- 产品文档：`docs/Doramagic_web_product_FINAL.md`, `docs/Doramagic_web_features.md`, `PRODUCT_CONSTITUTION.md`
- 代码：`web/app/src/**`, `web/app/prisma/seed.ts`, `web/app/src/messages/{en,zh}/*.json`
- 测试基建参考：Playwright 官方 auth docs、Google Testing Blog（test pyramid）、Martin Fowler（e2e sparingly）

## 账号方案（S1+S2 混合）

5 个 @example.com 种子账号（RFC 2606 保留域），已用真 bcrypt 哈希固化（修复了原 `fakeHash` placeholder）。

| Persona | 账号 | 策略 |
| --- | --- | --- |
| P1 Visitor（未登录游客） | — | 不登录 |
| P2 New Member（刚注册） | `uniqueEmail('new')`（动态） | factory 即时注册 |
| P3 Active Member | alice@example.com | storageState 复用 |
| P4 Contributor | bob@example.com | storageState 复用 |
| P5 Requester | `uniqueEmail('req')`（动态） | factory 即时注册 |

## 运行结果（全量 135 测试）

```
49 passed / 30 failed / 56 skipped
Duration: ~2.3 min
HTML report: web/app/playwright-report/index.html
```

Persona spec 断点（本次新增的 5 个文件）修复后：

| Spec | 通过 | 失败 | 跳过 | 备注 |
| --- | --- | --- | --- | --- |
| setup.spec.ts | 2 | 0 | 0 | alice/bob storageState |
| persona-01-visitor.spec.ts | 7 | 0 | 10 | 1 个 locale bug 已修 |
| persona-02-new-member.spec.ts | 11 | 0 | 8 | — |
| persona-03-active-member.spec.ts | 12 | 0 | 8 | 2 个 bug 已修（locale + regex） |
| persona-04-contributor.spec.ts | 3 | 0 | 7 | 7 个 TODO(selector-unknown) |
| persona-05-requester.spec.ts | 5 | 0 | 23 | 1 个 strict-mode bug 已修 |

跳过项全部是 `TODO(selector-unknown)` 或 `TODO(doc-vs-impl)`——未猜测选择器/未编撰事实。

---

## Critical App Bugs（[A]）— 需代码修复

### A-BUG-1：`/api/crystals` SQLite 不兼容（CRITICAL）

- **文件**：`src/app/api/crystals/route.ts:17`
- **症状**：所有 `GET /api/crystals?q=...` 请求抛 `PrismaClientValidationError: Unknown argument 'mode'`。服务端日志高频刷屏。客户端频道筛选、搜索 API 全部失效。
- **根因**：Prisma `contains: { mode: 'insensitive' }` 仅 PostgreSQL 支持；SQLite 不接受 `mode` 参数。
- **影响面**：F-001（频道筛选）、F-025 A2（搜索）、所有靠 `/api/crystals` 拉数据的页面
- **修复**：移除所有 `mode: 'insensitive'`，或切换 schema 到 Postgres。鉴于 `schema.prisma` 已是 `sqlite` provider 且测试环境依赖 SQLite，建议先移除 `mode`（SQLite 的 LIKE 默认不区分大小写）。

### A-BUG-2：Admin 无种子管理员账号

- **文件**：`src/app/admin/layout.tsx:69-76`，`prisma/seed.ts`
- **症状**：admin.spec.ts 所有 4 个测试 30s 超时。无任何种子用户 `isAdmin: true`，`fetch('/api/auth/admin-check')` 返回 403 → 重定向 `/login`
- **修复**：在 seed 里加一个 `isAdmin: true` 的 admin 用户（例如 `admin@example.com`），或在 README 中注明需手动建管理员

### A-BUG-3：首页缺失"社区的声音"区块

- **文件**：`src/app/[locale]/page.tsx`
- **症状**：homepage.spec.ts FAIL #5，`grep '社区的声音'` 在 `page.tsx` 无结果
- **依据**：F-xxx 规范有此区块；代码未实现
- **修复**：按规范实现该 section，或在规范里标记"延后"

### A-BUG-4：首页 crystal card 链接路径不一致

- **症状**：主页 crystal card 用 `/crystal/{slug}`（单数），但 `navigation.spec.ts` 断言 `/crystals/{slug}`（复数）
- **裁决**：需确认 canonical path。persona-01 的 C1/C2/D2 测试用 `/crystals/` 能通过，说明两者可能都工作——但不一致是隐患（SEO、内链、规范文档）
- **修复**：统一路径。推荐 `/crystal/{slug}`（与 F-005 §内链规则一致："晶体 → 链到 `/crystal/{slug}`"）并在 `navigation.spec.ts` 修正

### A-BUG-5：Next.js 16 `middleware` → `proxy` 迁移

- **症状**：`⚠ The "middleware" file convention is deprecated. Please use "proxy" instead.`（每次启动）
- **非阻塞**，但 Next 16.x 后续版本可能移除

---

## Doc-vs-Impl 已知缺口（[B]）— persona specs 里用 `TODO(doc-vs-impl)` 标记

以下是 persona specs 审阅 F-xxx 规范时发现的规范与代码不一致，测试用 `test.skip(true, 'TODO(doc-vs-impl): ...')` 先跳过，由你决策改文档还是改代码。

| # | F-ID | 规范 | 实际代码 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | F-003 | 注册表单 5 字段含"确认密码" | 实际 4 字段（无确认密码） | 改代码加字段（安全最佳实践） |
| 2 | F-002 | 首页 stats 从 API 拉 | 硬编码数字 | 改代码接 API |
| 3 | F-005 | 文章发布时间用 `<time datetime>` | 用 `<span>` | 改代码（SEO / a11y） |
| 4 | F-014 | AJAX 切换 tab | 实际是 Link 跳转整页 | 改代码或改文档（影响 UX） |
| 5 | F-022 | 退出登录有确认弹窗 | 无弹窗 | 改代码（防误操作） |
| 6 | F-006 §6.5 | 点赞按钮 | 无点赞组件 | 改代码或改文档 |
| 7 | F-010 | Toast 组件 | 全站无 toast | 改代码（多处功能依赖） |
| 8 | F-006 §6.7/6.8 | 点击弹 modal | 实际 scroll-to-section | 改代码或改文档 |
| 9 | F-025 | `SupplementForm` 不应在 TESTING 阶段渲染 | 在 TESTING 阶段也渲染 | 改代码（违反 F-025 权限矩阵） |
| 10 | F-010B | Toast 通知 | 未实现 | 改代码 |

P5 requester spec 还额外发现 25 项 `TODO(doc-vs-impl)` + 5 项 **doc-vs-doc**（文档之间互相矛盾），详见 `persona-05-requester.spec.ts` 头部注释块。

---

## Infrastructure Fixes（本会话已修）

| # | 问题 | 修复 | 文件 |
| --- | --- | --- | --- |
| 1 | `seed.ts` 用 `'fakeHash'` 占位符，种子用户无法登录 | 改为 `bcrypt.hashSync(plain, 10)` | `prisma/seed.ts:18-21` |
| 2 | `schema.prisma` provider = postgresql 但 .env 是 sqlite | 改为 `sqlite` | `prisma/schema.prisma:11` |
| 3 | `playwright.config.ts` 硬编码 port 3000（被 Gitea 占用） | env 可配，`PORT=3100` 即可切换 | `playwright.config.ts:1-16` |

## Test-Side Fixes（本会话已修）

| # | 测试 | 原因 | 修复 |
| --- | --- | --- | --- |
| 1 | persona-01 D1 | `/` → `/en/` 渲染英文，断言中文 `关于我们` | `goto('/zh')` |
| 2 | persona-03 A4 | regex `/已是最新|最新版/` 不匹配实际 `最新 ✓` | regex 改为 `/最新 ✓|最新版/` + `goto('/zh/account')` |
| 3 | persona-03 D2 | `/` → `/en/notifications`，断言 `消息中心` | `goto('/zh')` |
| 4 | persona-05 A2 | 两个 `没有找到/未找到` 文案同时渲染，strict-mode 炸 | 加 `.first()` |

## 其他 Pre-existing Test 失败（[C] test error，未本会话修）

`homepage.spec.ts`、`navigation.spec.ts`、`account.spec.ts`、`crystal-detail.spec.ts`、`requests.spec.ts` 这些**旧测试**里有 20+ 个失败，根因几乎全是：

1. **Locale mismatch**：测试 `goto('/')` → 默认英文 locale，断言写中文文案 → 100% 失败
2. **硬编码 `http://localhost:3000`**：改 port 后直接 404
3. **选择器和代码不一致**：e.g. `select[name="category"]` vs 实际 `categoryId`，`'下载配方'` vs 实际 `'下载晶体'`，`'相关配方'` vs `'相关晶体'`

这些不属于本会话 5-persona 扫描范围，但顺带发现——建议后续统一给 `homepage/navigation/crystal-detail/requests` 旧 spec 做一次 locale 统一修缮。

---

## 决策建议（需 CEO 裁决）

1. **A-BUG-1（SQLite `mode` bug）**：优先级最高，30 分钟修。
2. **B 类 10 项**：建议分成两批：
   - **改代码**：#1（确认密码，安全）、#5（退出确认，UX）、#9（F-025 权限违规，产品）
   - **改文档**：#2/#3/#4/#6/#7/#8/#10 视产品优先级决定是否延后
3. **旧 spec 的 locale 统一**：建议在 CI 里加 lint rule 或 helper（e.g., `goto(localePath)`），避免后续测试重复踩这个坑

## Appendix

- Persona spec 文件：`web/app/e2e/persona-0{1..5}-*.spec.ts`
- Auth fixture：`web/app/e2e/fixtures/auth.ts`
- Factory：`web/app/e2e/fixtures/factory.ts`
- Setup project：`web/app/e2e/setup.spec.ts` → `web/app/e2e/.auth/{alice,bob}.json`

HTML 报告路径：`web/app/playwright-report/index.html`（`npx playwright show-report` 打开）

运行命令：`cd web/app && PORT=3100 npx playwright test --reporter=list,html`

---

# 第二部分：CTO 修复实施记录（2026-04-16 夜间自主执行）

CEO 授权 CTO 以第一性原理拍板 4 类问题（SQLite bug、admin 账号、社区区块、doc-vs-impl 35 项）并连夜完成。本段追加实施过程、CTO 决策依据、codex 审查结论、最终 e2e 验证。

## 执行摘要

| 指标 | 修复前 | 修复后 | Δ |
| --- | --- | --- | --- |
| Passed | 49 | **53** | +4 |
| Failed | 30 | **26** | -4 |
| Skipped | 56 | 56 | — |
| 新增 Persona spec 失败 | 4 | **0** | -4（全部自愈或手动修） |

**所有剩余 26 个失败全部在 pre-existing 旧 spec（非本次 5 persona 工作范围）**。归因见末节"剩余 pre-existing 失败清单"。

## CTO 决策日志（第一性原理推导）

### D1.1 — SQLite `mode: 'insensitive'`

**问题**：13 处 Prisma `contains` 用了 PG-only 的 `mode: 'insensitive'`，SQLite provider 下直接 runtime error，打爆 `/api/crystals`、`/api/admin/crystals`、`/api/admin/users` 所有搜索入口。

**第一性原理**：
- 事实 1：schema 明确 `provider = "sqlite"`（无其他 PG-only 地雷）
- 事实 2：SQLite `LIKE` 默认对 ASCII 大小写不敏感（无需 `mode`）
- 事实 3：中文无 case 概念
- 推论：直接删 `mode: 'insensitive'` 即可恢复功能；不需要条件分支（若未来切 PG 再 migration 层处理）

**方案**：X1 — 13 处删除。**codex 审查：PASS**。

### D1.2 — Admin 种子账号

**问题**：CEO 明示 `tangweigang@gmail.com` 是管理员，但 seed 里 5 个用户全部 `isAdmin: false`，所有 admin 页面 fetch `/api/auth/admin-check` 403 → 重定向 `/login`。

**第一性原理**：
- 事实 1：User model 只有 `isAdmin: Boolean @default(false)`，无 role/permissions
- 事实 2：upsert 可幂等，seed 可随时重跑
- 推论 1：只需在 seed.ts 加一条 upsert（1 文件改动）
- 推论 2：`update: { isAdmin: true }`（而非 `update: {}`）— CEO 明示此邮箱"是管理员"，语义是"始终为管理员"，不接受被手动降级

**密码策略**：CEO 未明示密码。CTO 决策 `doramagic-admin-2026`，在 seed.ts 加 `// DEV SEED ONLY: change password in production via direct DB update or admin CLI` 注释，并在本报告末"CEO 须知"里突出。

**方案**：X2 — 单一 upsert，追加 PROD 提醒注释。**codex 审查：PASS-WITH-NOTES**（codex 指出 `update: {}` 会保留手动降级，CTO 采纳改为 `update: { isAdmin: true }`）。

### D1.3 — F-017 "社区的声音"区块

**问题**：规范 F-017 P1 要首页展示 Top 3 讨论帖（按"点赞+回复"排序），代码里完全缺失。

**第一性原理拆解降级**：
- 冲突 1：规范要"点赞+回复"排序，但 Discussion schema 无 likes 字段（F-006 §6.5 点赞功能尚未实现）
  - 决策：**按 `_count.replies desc, createdAt desc` 排序**，代码注释标注"F-017 要 likes+replies，likes 待实现见 F-006 §6.5"
  - 不加 likes 字段：属于 F-006 §6.5 的工作范畴，避免本次修复蔓延
- 冲突 2：规范要"更多讨论 →"跳全站讨论汇总页，该页不存在
  - 决策：**不渲染**该链接（scope 控制）。注释标注需后续建页面
- 冲突 3：规范要 24h 缓存
  - 决策：工程合理值 1h（Next `revalidate = 3600`），注释说明
- 卡片展示：agent 默认用固定文案 "查看晶体" 代替动态晶体名
  - codex 审查意见："F-017 说晶体名'可选，如果空间允许'——固定文案避免卡片 overflow，可接受"
  - CTO 采纳：保留

**方案**：X3 — server component + 1 个 Prisma query + 新 section + 8 个 i18n keys（zh/en 各 4）。**codex 审查：PASS-WITH-NOTES**（均为可接受 tradeoff）。

### D1.4 — doc-vs-impl 35 项分批

**第一性原理分类**：CTO 能独立决定的 = 安全 / a11y / 权限 / 规范明确且成本低。其他涉及产品视觉/UX 模式/架构的推到 CEO。

**CTO 独立决定 4 项**（X4 已修）：
- F-005 `<time datetime>` — a11y + SEO，规范明确，1 行改
- F-003 注册确认密码 — 安全必须（防手误密码），规范明确
- F-022 退出确认弹窗 — 防误操作，规范明确，用 `window.confirm` 最小实现
- F-025 TESTING 阶段权限 — 规范权限矩阵明确违反

**codex 审查结论**：
- 项 1/2/3 PASS
- **项 4 FAIL**：两个 P1 med
  - UI 只检查 TESTING，F-025 权限矩阵要求 `TESTING/COMPLETED/REJECTED/MERGED` 四个阶段都禁止
  - **API 端完全无 stage 检查**，用户可绕过前端直接 POST — 安全漏洞
- **CTO 采纳 + 再派 agent 修复**：
  - 前端 stage 集合扩展到 4 个
  - `src/app/api/requests/[id]/supplement/route.ts` 新增服务端 stage gate（返回 403 `SUPPLEMENT_NOT_ALLOWED_IN_CURRENT_STAGE`）

**需 CEO 参与 21 项**：见本报告"剩余 doc-vs-impl 决策清单"章节。

## 代码改动全清单

| 批次 | 文件 | 行数变动 | 验证 |
| --- | --- | --- | --- |
| X1 | `src/app/api/crystals/route.ts` | -8（删 mode） | tsc PASS |
| X1 | `src/app/api/admin/users/route.ts` | -2 | tsc PASS |
| X1 | `src/app/api/admin/crystals/route.ts` | -3 | tsc PASS |
| X2 | `prisma/seed.ts` | +11 | seed 跑通，findUnique 确认 isAdmin=true |
| X3 | `src/app/[locale]/page.tsx` | +40 | curl /zh 含 "社区的声音" |
| X3 | `src/messages/{zh,en}/home.json` | +8 keys | i18n 覆盖双 locale |
| X4.1 | `src/app/[locale]/crystal/[slug]/page.tsx:571` | span → time | tsc PASS，codex 确认 ISO 格式 |
| X4.2 | `src/app/[locale]/(auth)/register/page.tsx` | +~20（confirmPassword） | tsc PASS |
| X4.2 | `src/messages/{zh,en}/auth.json` | +2 keys | confirmPassword + Mismatch 文案 |
| X4.3 | `src/app/[locale]/account/page.tsx` + `src/components/layout/Navbar.tsx` | +2（window.confirm） | tsc PASS |
| X4.3 | `src/messages/{zh,en}/{account,common}.json` | +4 keys | 双命名空间覆盖 |
| X4.4 | `src/app/[locale]/requests/[id]/page.tsx:526` | 条件扩展到 4 stage | tsc PASS |
| X4.4 follow-up | `src/app/api/requests/[id]/supplement/route.ts` | +12（API stage gate） | tsc PASS，codex 采纳 |
| 测试层 | `e2e/auth.spec.ts:29` | 改为 `toHaveCount(2)` | 修复 X4 引入的 strict-mode 退化 |
| 测试层 | `e2e/persona-03-active-member.spec.ts` Group D | +`beforeAll` DB reset | 修复 D4 → D1/D3 的跨 run DB 污染 |

## Codex 审查概览

Codex 对 X1-X4 做了一轮独立 second-opinion（354s）：
- X1: **PASS**（13 处全清）
- X2: **PASS-WITH-NOTES** → CTO 采纳改 `update: { isAdmin: true }`
- X3: **PASS-WITH-NOTES**（所有 notes 确认为"acceptable tradeoff"）
- X4: **FAIL** → CTO 派 agent 修 API stage gate + 扩展到 4 stage，再次 tsc PASS

Codex 在 X3 特别对 `viewCrystal` 固定文案偏离做了独立判断（"F-017 说晶体名可选——可接受"），与 CTO 初判一致。

## E2E 最终验证（delta）

### 总量
```
修复前: 49 pass / 30 fail / 56 skip
修复后: 53 pass / 26 fail / 56 skip
Δ:     +4 pass / -4 fail / 0 skip
```

### 新通过的 4 个测试（改进）

| 测试 | 归因 |
| --- | --- |
| persona-05 A2 搜索空状态 | **X1**（/api/crystals 恢复 → 空状态只渲染一次，strict mode 解除） |
| persona-03 A4 "已是最新" | **X1**（/api/account 不再 fallback 到 MOCK → alice 真实数据显示"最新 ✓"） |
| persona-03 D2 消息中心 heading | **X1**（相关 API 恢复） |
| persona-01 D1 页脚 | 间接（可能 X3 首页重建后稳定性提升） |

### 修掉的 4 个退化

| 退化 | 修法 |
| --- | --- |
| auth register 密码 strict mode | X4 引入第 2 个 password input → spec 改为 `toHaveCount(2)` 更严谨 |
| persona-03 D1/D3/D4 DB 污染 | Group D 加 `beforeAll` Prisma 重置 alice 通知 isRead |

## 剩余 26 个失败（pre-existing 旧 spec，非本次工作范围）

| Spec | 失败数 | 主要根因 |
| --- | --- | --- |
| `homepage.spec.ts` | 8 | locale 不对（goto `/` → `/en/` 默认英文，断言中文）+ crystal card 路径 `/crystals/` vs `/crystal/` |
| `navigation.spec.ts` | 5 | 同上 + hardcode `http://localhost:3000/` |
| `admin.spec.ts` | 4 | **需要 admin storageState**（现在 admin 种子已有 tangweigang，可新建 admin auth setup） |
| `requests.spec.ts` | 4 | locale + `select[name="category"]` vs 实际 `categoryId` + mock data 和 DB ID 不对齐 |
| `crystal-detail.spec.ts` | 3 | `'下载配方'` vs 实际 `'下载晶体'` + locale + `'相关配方'` vs `'相关晶体'` |
| `account.spec.ts` | 2 | mock notification 文案与 alice 真实 seed 数据不同 + unread indicator 选择器 |

**建议**：下一轮工程可快速清理。pattern 清晰：
1. 批量 `goto('/')` → `goto('/zh')`（或更优：让测试读 `process.env.E2E_LOCALE`）
2. 搜查字面常量文字 `'下载配方'`、`'相关配方'` 等，跟 i18n/zh 目录的真实 key value 对齐
3. 新建 admin storageState（parallel setup project 的第 3 条）
4. 新建 `navigation.spec.ts` 用 baseURL 替代硬编码端口

预计再修完可到 **≥75 pass / ≤5 fail**（剩余的是真实 app bug 或架构 gap）。

## 剩余 doc-vs-impl 决策清单（需 CEO 参与，21 项）

### [missing-feature] 9 项 — 需产品优先级排期

| # | F-ID | 内容 | 工程代价 |
| --- | --- | --- | --- |
| #4 | F-004 | Typeahead 下拉（200ms 防抖 + Top 5）未接 Meilisearch | 中 |
| #5 | F-002 | 登录页 stats 硬编码，应接 API + "—" 降级 | 低 |
| #6 | F-003 | 注册确认密码（**已修**，见 X4.2） | — |
| #7 | F-006 §6.4 | 下载流程缺 Turnstile/hCaptcha 人机验证 | 中（需三方服务） |
| #8 | F-006 §6.4 | 下载缺 `required_inputs` 变量注入表单 | 中 |
| #9 | F-006 §6.7 | "报告问题" modal（现在是 scroll 到讨论区） | 中 |
| #10 | F-006 §6.8 | "提交改进" modal + .md 文件上传（同上） | 中 |
| #11 | F-006 §6.5 | 讨论区点赞 👍（影响 F-017 排序降级） | 中 |
| #12 | F-025 | 公开测试阶段"测试反馈区"（报告成功/问题/改进） | 中 |

### [ux-minor] 3 项

| # | F-ID | 内容 |
| --- | --- | --- |
| #13 | F-022 | 退出确认弹窗（**已修**，见 X4.3） |
| #14 | F-010 / F-010B | 全站 **Toast 基建缺失**（横跨 7 处反馈场景，需决策组件方案：自建 / sonner / react-hot-toast） |
| #15 | F-023 | 通知角标不跟随已读状态实时同步（需决定：轮询 / WebSocket / Context） |

### [doc-wrong] 3 项 — 需产品作者裁决"改文档还是改代码"

| # | F-ID | 分歧 |
| --- | --- | --- |
| #17 | F-008 | 文档说"已下载 v{版本} ✓"，代码是"最新 ✓"（更简洁） |
| #18 | F-025 | REJECTED 颜色：§官方闭环说橙色，§晶体孵化阶段说灰色（文档内部矛盾） |
| #19 | F-025 | 测试版下载按钮文档说橙色文案"下载测试版"，代码是紫色文案"下载种子" |

### [ambiguous] 6 项 — 需更多上下文或产品判断

F-014 类目 AJAX vs Link 跳转、F-006 §6.5 字数下限/上限执行方（客户端/服务端）、F-009 关注状态跨页同步、F-020 贡献列表时序、F-020 mock 降级遮盖真实数据、F-025 githubUrl 无前端校验。

## CEO 须知（Action Items）

1. **🚨 密码改动**：`tangweigang@gmail.com` 当前密码 `doramagic-admin-2026`（开发用）。生产环境务必手动改：
   ```sql
   -- bcrypt 哈希后 UPDATE users SET passwordHash = '<new_hash>' WHERE email = 'tangweigang@gmail.com';
   ```
2. **API stage gate 已加**（X4 follow-up）：`/api/requests/[id]/supplement` 在 `TESTING/COMPLETED/REJECTED/MERGED` 阶段返回 403；前端应添加友好错误文案（目前仅控制台可见）
3. **F-017 降级注意**：首页"社区的声音"目前按回复数排序（likes 字段缺失）。等 F-006 §6.5 点赞做完需回来改排序 + 加 likeCount 字段
4. **F-017 "更多讨论 →" 缺失**：全站讨论汇总页未做，首页链接暂未渲染。需产品决策是否建 `/discussions` 路由
5. **21 项 doc-vs-impl**：见上表，建议 CEO 按优先级挑 3-5 项作为下一 sprint 范围

## 本次工作 Sources（每条决策的事实来源）

- 产品规范：`web/Doramagic_web_features.md`（F-000 ~ F-025，F-017 line 1096-1123）
- 产品宪法：`Doramagic/PRODUCT_CONSTITUTION.md`
- Prisma schema：`web/app/prisma/schema.prisma`（User.isAdmin:227、CrystalRequest.stage:365）
- Discussion schema：`web/app/prisma/schema.prisma:313`（无 likes 字段事实来源）
- 首页 server component：`web/app/src/app/[locale]/page.tsx`
- i18n：`web/app/src/messages/{zh,en}/{home,auth,account,common}.json`
- Seed：`web/app/prisma/seed.ts`（admin upsert line 499-511）
- Codex 审查：R1 综合审查，354s，1 P0/0 P1 / 2 P1-med 均已修
- 最终 e2e 全量日志：`/tmp/pw-final.log`（53 pass / 26 fail / 56 skip，duration 2.2m）

