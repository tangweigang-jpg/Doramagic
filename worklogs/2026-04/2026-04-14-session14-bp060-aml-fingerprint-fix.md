# 工作日志：bp-060 AMLSim 全自动提取 + 指纹探针修复

> 日期：2026-04-14
> 会话：session 14（约 2.5 小时）
> 目标：验证 v6.4 agent 对 AML 子领域的全自动提取能力

---

## 一、MiniMax 模型配置修正

### 发现

通过研究 MiniMax 官方文档，发现两个配置问题：

1. **模型名错误**：使用 `MiniMax-M2.7` 但用户套餐（Max 极速版）对应的是 `MiniMax-M2.7-highspeed`
2. **并发过高**：6 个并行 worker 触发 Token Plan 的并发限制（Max 套餐约支持 2-3 个并发 agent）

### 关键数据

- MiniMax-M2.7-highspeed 与 MiniMax-M2.7 **推理能力完全相同**，官方 FAQ："效果相同"
- highspeed 提供 ~100 TPS 极速推理
- Max 套餐：4500 次/5 小时，高峰期（15:00-17:30）约 2 并发 agent

### 修复

- `.env`：`LLM_MODEL=MiniMax-M2.7-highspeed`
- `orchestrator.py`：blueprint executor `max_parallel=3`（从默认 5 降低）
- 8 个 worker 分 3 波执行（3+3+2），而非 2 波（6+2）

---

## 二、bp-060 v1 提取（指纹错误）

### MiniMax 过载事件

首次提取遭遇 MiniMax 服务端持续 529 过载 + 429 限流：
- 6 个并行 worker 同时触发 429
- Failover 到 GLM-5 后 token 预算超限（510K/500K）
- Pipeline 中断，3 次 resume 均失败

### 模型切换后成功

切换到 highspeed + max_parallel=3 后，零限流完成提取：
- QG: 8/9 PASS（BQ-03 multi_type 21.1% 未达 30%）
- Synthesis Step 1-3 全部 L2 直接成功（首次！）
- Assembly 也 L2 直接成功（首次！）
- 616K tokens，全自动

### 定量评估暴露问题

评估得分 58/100，核心问题：**AML 子领域被误标为 AIL**
- 指纹探针只读 README + 文件名/目录名
- AMLSim 是 Java 项目，Python 文件内容中的 `aml`/`suspicious` 未被扫描
- 导致 AML 专项审计清单（SOP v3.5 新增 6 项）完全未执行

---

## 三、指纹探针修复

### 根因

`fingerprint_repo()` 搜索范围：README + .py 文件名 + 目录名。不读 .py 文件内容。

### 修复（三层递进）

1. **加入仓库根目录名**：`AMLSim` 包含 `aml` 关键词
2. **读 .py 文件前 5 行**：module docstring 通常描述模块用途
3. **读 setup.py/pyproject.toml**：项目元数据有领域描述
4. **AML 关键词精确化**：`\baml\b`（word boundary）避免匹配 "yaml"/"caml"；增加 `money.laundering`/`anti.money`/`typolog`
5. **移除 `screening`**：太泛，信用评分也用（false positive 源）

### 验证

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| AMLSim | AIL（错） | **CRD + AIL + AML** ✅ |
| zvt | TRD/A_STOCK/... | TRD/A_STOCK/...（无 AML 误报）✅ |
| skorecard | CRD/DAT | RSK/CRD/DAT（无 AML 误报）✅ |

---

## 四、bp-060 v2 提取（指纹修复后）

### 结果

| 指标 | v1（指纹错误）| v2（指纹修复）|
|------|------------|--------------|
| QG | 8/9 | **9/9 ALL PASS** |
| 子领域 | AIL | **CRD + AIL + AML** |
| non-T BDs | 76 | 64 |
| Multi-type | 21.1% | **32.8%** |
| Missing gaps | 8（通用） | **9（含 AML 专项）** |
| Rationale | 249 chars | **320 chars** |
| P5.5 ratio | 33.3% | 27.6% |
| Tokens | 616K | 592K |
| 全自动 | yes | **yes** |

BQ-03 从 WARN 变为 PASS（AML 审计清单驱动了更好的类型标注）。

---

## 五、四项目全自动提取汇总

| 项目 | 版本 | QG | non-T | Gaps | UCs | Tokens | 全自动 |
|------|------|-----|-------|------|-----|--------|--------|
| bp-050 skorecard | v3 | 9/9 | 88 | 14 | 19 | 1,258K | yes |
| bp-009 zvt | v11 | 9/9 | 89 | 5 | 32 | 971K | yes |
| bp-060 AMLSim | v1 | 8/9 | 76 | 8 | 0 | 616K | yes |
| **bp-060 AMLSim** | **v2** | **9/9** | **64** | **9** | **0** | **592K** | **yes** |

三个不同子领域（TRD/CRD/AML）的项目均实现全自动提取 QG 9/9 PASS。

---

## 六、Commit 记录

| Commit | 内容 |
|--------|------|
| `98df150` | 指纹探针修复 + max_parallel 3 + AML 关键词精确化 |

---

## 七、遗留问题 & 下一步

1. **Evidence 质量仍是最大短板**：v2 的 P5.5 ratio 仅 27.6%（54 条 invalid），需要改进 LLM prompt 对 evidence 格式的约束
2. **Assembly L2 成功率不稳定**：v1 全 L2 pass，v2 走了 L3 fallback（`design_decisions` 返回 dict 而非 string）
3. **P0 剩余 10 个项目**：bp-061~070 待提取
4. **非代码类知识提取**：用户确认 Doramagic 应支持 AI skill/prompt 类项目提取（如 nuwa-skill），需要设计新的提取范式

### 下一个会话方向

**讨论非代码类知识资产提取**：越来越多的 AI 类项目（prompt engineering、cognitive framework、agent skill）在 GitHub 出现，代表未来趋势。需要设计超越"源码 → pipeline → BD"的新提取范式，支持 .md/.txt 为主的知识项目。
