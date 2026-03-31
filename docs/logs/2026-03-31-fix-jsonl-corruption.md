# 修复 knowledge/bricks/ JSONL 文件格式损坏
日期: 2026-03-31
执行者: Claude Code

## 做了什么

扫描 knowledge/bricks/ 中全部 50 个 JSONL 文件，发现 9 个文件共 318 行无法被 json.loads() 解析，逐一修复并写回原文件。

**修复前后对比：**
- 损坏行数：318 行（跨 9 个文件）
- 修复后损坏行数：0
- 总条目数：修复前 10028 条，修复后 10028 条（零损失）
- make check：489 tests passed

## 损坏文件清单

| 文件 | 损坏行数 | 主要损坏类型 |
|------|---------|-------------|
| domain_finance.jsonl | 100 | 行末多余逗号（JSON 数组格式） |
| domain_health.jsonl | 150 | 行末多余逗号（JSON 数组格式） |
| domain_pkm.jsonl | 43 | 行末多余逗号 42 行 + 非法转义 1 行 |
| typescript_nodejs.jsonl | 13 | 非法转义（\\\` 反引号）12 行 + 单引号包裹的未转义双引号 1 行 |
| obsidian_logseq.jsonl | 4 | 单引号包裹内容中有未转义的双引号 |
| domain_private_cloud.jsonl | 3 | 非法转义（\\|）1 行 + 单引号包裹未转义双引号 2 行 |
| dspy.jsonl | 3 | null 值后多余引号（null" -> null） |
| java_spring_boot.jsonl | 1 | Java 注解语法中的集合字面量未转义 |
| web_browsing.jsonl | 1 | 单引号包裹内容中有未转义的双引号 |

## 损坏根因分析

这些 JSONL 文件由 LLM 生成，存在 5 类格式问题：

1. **行末逗号**（255 行）：文件以 JSON 数组格式生成（每行末有 `,`），而非标准 JSONL（每行独立 JSON 对象）。去掉末尾逗号即可。

2. **null 后多余引号**（3 行）：`"end_line":null","snippet"` → 应为 `"end_line":null,"snippet"`，引号位置写错。

3. **非法 JSON 转义序列**（14 行）：JSON 只允许 `\"  \\  \b \f \n \r \t \uXXXX` 等转义。文件中出现了 `\`` `\'` `\|` 等非法序列。修复：去掉转义符中的反斜杠。

4. **单引号包裹的内容含未转义双引号**（8 行）：在 JSON 字符串值内部，嵌入了 shell 命令或代码示例，如 `'{"spec":{"suspend":true}}'`，其中的双引号未被转义为 `\"`，导致 JSON 解析器误以为字符串提前结束。

5. **Java 注解集合字面量**（1 行）：`={\"com.example\", \"com.shared\"}` 这类 Java 语法里的双引号未正确转义。

## 修复策略

按优先级依次尝试，找到第一个能让 json.loads() 成功的修复：

1. 去末尾逗号
2. 替换 `null"` 为 `null`
3. 正则去除非法转义字符前的反斜杠：`re.sub(r"\\([^\"\\bfnrtu/\n])", r"\1", line)`
4. 将单引号包裹的内容中的 `"` 替换为 `\"`
5. 将 `=\{...\}` 模式中的 `"` 替换为 `\"`

## 遇到的问题

- 损坏类型 4（单引号包裹未转义双引号）最难发现：Python repr 会将单引号显示为 `\'`，初看以为是非法转义，实际上单引号在 JSON 字符串中是合法字符，真正的问题是其内部的双引号
- raw bytes 分析帮助识别实际字符编码，排除了 Python repr 带来的误导

## 下一步

- 建议 brick 生成流程加入 JSONL 格式验证步骤（每行 json.loads() 检查），防止类似问题再次进入文件
- 如有需要，可将本 fix 脚本迁移为 `scripts/validate_bricks.py` 并加入 CI
