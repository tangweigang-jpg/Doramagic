# Doramagic 极限模拟：食物卡路里追踪 Skill 组装报告

> 日期：2026-03-17
> 输入：3 个开源项目灵魂提取 + 4 个社区 skill 调研 + LobsterLair 架构
> 输出：一个可交付的 OpenClaw skill 设计方案

---

## 一、知识来源总览

| 来源 | 类型 | 贡献重点 |
|------|------|---------|
| **ai-calorie-counter** | 开源项目 | AI 拍照/文字→JSON 契约、BMR 计算、上下文动态注入 |
| **FoodYou** | 开源项目 | 42 字段完整营养素 schema、4 数据库来源、食谱系统、空值语义 |
| **OpenNutriTracker** | 开源项目 | IOM2005 TDEE 公式、运动 MET 值库、双数据库搜索策略、TrackedDay 快照 |
| **ClawHub 4 个 skill** | 社区 skill | 存储路径标准、三餐提醒 cron、日/周/月查询 |
| **LobsterLair** | 社区教程 | 视觉模型架构、人格层、Apple Health 集成 |

---

## 二、公约数（所有来源的共识知识）

### 共识 1：AI 识别 + 数据库查询双轨

- ai-calorie-counter：纯 AI 估算（视觉模型/文字描述）
- FoodYou/OpenNutriTracker：纯数据库查询（OFF + FDC）
- LobsterLair：AI 识别为主

**共识**：两者不是互斥的。AI 识别快但不精确（80-90%），数据库精确但需要用户手动搜索。**最佳方案是 AI 先估 → 用户可选数据库校准**。

### 共识 2：Mifflin-St Jeor / IOM 2005 是首选 TDEE 公式

- ai-calorie-counter：Mifflin-St Jeor
- OpenNutriTracker：IOM 2005（更精确，含性别细分 PA 系数）
- FoodYou：未内置 BMR 计算（只有目标设定）

**共识**：IOM 2005 是最优选，Mifflin-St Jeor 作为备选。

### 共识 3：存储格式为每日 Markdown 日志

- ClawHub 4 个 skill：`~/clawd/memory/YYYY-MM-DD.md`
- LobsterLair：`health/meals/YYYY-MM-DD.md`

**共识**：OpenClaw 生态标准是 Markdown 文件，按日期命名。不需要数据库。

### 共识 4：三餐 + 零食的分类结构

- FoodYou：早/午/晚/零食 4 类
- OpenNutriTracker：早/午/晚/零食 4 类
- ClawHub skills：三餐提醒 cron（8AM/1PM/7PM）

**共识**：4 个餐次分类是行业标准。

### 共识 5：运动消耗追踪是必备功能

- ai-calorie-counter：AI 估算运动消耗
- OpenNutriTracker：MET × 体重 × 时长，内置 80+ 种运动
- LobsterLair：Apple Health 自动拉取

**共识**：运动消耗必须纳入每日热量平衡。

---

## 三、各来源独创知识（用于差异化）

| 来源 | 独创知识 | 采纳？ |
|------|---------|--------|
| **ai-calorie-counter** | "消息即数据容器"范式（聊天记录=追踪日志） | ✅ 非常适合 OpenClaw 的消息驱动架构 |
| **ai-calorie-counter** | 聚合数据注入 AI 上下文（传今日总量而非全部记录） | ✅ 减少 token 消耗，提升建议质量 |
| **ai-calorie-counter** | AI 输出 JSON 契约（固定格式，前端拦截渲染） | ✅ 核心技术模式 |
| **FoodYou** | Complete/Incomplete 空值语义 | ⚠️ 记录但简化——skill 层不需要 42 字段精度 |
| **FoodYou** | ManualDiaryEntry（"不知道吃什么，只知道大约多少卡"） | ✅ 降低追踪门槛的关键 UX |
| **FoodYou** | Recipe.unpack(weight)（"我只吃了三分之一"） | ⚠️ V2 功能 |
| **FoodYou** | CJK 搜索需要专项处理（FTS5 不支持中文分词） | ✅ 中文用户关键暗坑 |
| **OpenNutriTracker** | TrackedDay 快照（历史不受设置变更影响） | ✅ 数据完整性设计 |
| **OpenNutriTracker** | 双数据库搜索策略（OFF 做品牌/条码，FDC 做食材） | ⚠️ 可选增强 |
| **OpenNutriTracker** | 80+ 种运动 MET 值数据 | ✅ 直接复用 |
| **LobsterLair** | 人格层（SOUL.md 配置鼓励型/毒舌型） | ✅ OpenClaw 天然支持 |
| **LobsterLair** | Apple Health 集成（自动拉取步数/运动） | ⚠️ iOS/macOS 限定 |
| **Community** | 日/周/月三档查询粒度 | ✅ 基本功能 |

---

## 四、组装：食物卡路里追踪 Skill 设计

### 4.1 Skill 定位

> **一句话**：拍照或说一句话记录你吃了什么，AI 自动算卡路里，每天告诉你还能吃多少。

**不是**一个完整的营养学 App（FoodYou 那种 42 字段的精度），**是**一个轻量级的 AI 助手（ai-calorie-counter + LobsterLair 的体验）。

### 4.2 核心功能（V1）

| 功能 | 触发方式 | 背后逻辑 |
|------|---------|---------|
| **记录食物** | 发照片 / 说"我吃了一碗面" | AI 视觉/文字 → JSON（名称/重量/卡路里/蛋白质/碳水/脂肪）→ 写入当日日志 |
| **记录运动** | 说"跑步 30 分钟" | AI 识别运动类型 → MET 值 × 体重 × 时长 → 写入当日日志 |
| **今日余量** | 说"我还能吃多少" | 读取当日日志 → TDEE - 已摄入 + 运动消耗 → 返回剩余卡路里和三大营养素 |
| **快速记录** | 说"大约 500 卡" | 不查数据库，直接记录热量（ManualDiaryEntry 理念） |
| **每日总结** | 晚 9 点自动推送 / 说"今天总结" | 聚合当日数据 → 与目标对比 → 给评价 |
| **历史查看** | 说"上周吃了什么" | 读取对应日期的日志文件 → 聚合 → 返回 |

### 4.3 用户引导（首次使用）

```
Doramagic：你好！我是你的卡路里助手 🦞
  需要了解你一些基本信息来计算每日热量目标：
  1. 性别？
  2. 年龄？
  3. 身高体重？
  4. 活动水平？（久坐/轻度/中度/重度）
  5. 目标？（减重/维持/增重）

→ 计算 TDEE（IOM 2005）
→ 展示："你的每日热量目标是 1800 kcal（蛋白质 90g / 碳水 225g / 脂肪 60g）"
→ "随时发食物照片或告诉我你吃了什么，我来帮你记！"
```

### 4.4 数据存储

```
~/clawd/memory/health/
├── profile.md          # 用户档案（性别/年龄/体重/TDEE）
├── meals/
│   ├── 2026-03-17.md   # 当日食物日志
│   ├── 2026-03-16.md
│   └── ...
└── summary/
    └── weekly-2026-W11.md  # 周报（自动生成）
```

**每日日志格式**（meals/YYYY-MM-DD.md）：

```markdown
# 2026-03-17 食物日志

## 目标
- TDEE: 1800 kcal | 蛋白质: 90g | 碳水: 225g | 脂肪: 60g

## 早餐
- 08:15 | 全麦面包 2 片 | 180 kcal | P:8g C:30g F:3g
- 08:15 | 煎蛋 1 个 | 90 kcal | P:6g C:1g F:7g

## 午餐
- 12:30 | 牛肉面一碗 | 550 kcal | P:25g C:65g F:18g

## 晚餐
（尚未记录）

## 零食
- 15:00 | 苹果 1 个 | 95 kcal | P:0g C:25g F:0g

## 运动
- 18:00 | 跑步 30 分钟 | -280 kcal

## 今日汇总
- 已摄入: 915 kcal | 运动消耗: 280 kcal
- 净摄入: 635 kcal
- 剩余: 1165 kcal
```

### 4.5 AI Prompt 契约（核心）

从 ai-calorie-counter 提取的 JSON 契约模式：

```
当用户描述食物时，返回 JSON：
{
  "type": "food",
  "time": "12:30",
  "meal": "lunch",
  "name": "牛肉面",
  "weight": 450,
  "calories": 550,
  "protein": 25,
  "carbs": 65,
  "fat": 18
}

当用户描述运动时，返回 JSON：
{
  "type": "activity",
  "time": "18:00",
  "name": "跑步",
  "duration": 30,
  "caloriesBurned": 280
}

回答建议时，先读取当日已有数据（以聚合摘要形式注入上下文）：
已摄入: {calories: 915, protein: 39, carbs: 121, fat: 28}
TDEE: 1800
运动消耗: 280
```

### 4.6 人格配置（从 LobsterLair 借鉴）

在 SOUL.md 中配置：

```markdown
# 人格：温暖鼓励型
- 每次记录后给予正面反馈（"不错！蛋白质摄入很充足"）
- 超标时温和提醒（"今天碳水有点多了，晚餐可以少吃点主食"）
- 连续记录 7 天给予成就感（"坚持一周了！"）
```

### 4.7 提醒 cron

```
8:00  早餐提醒："早上好！记得记录早餐 🌅"
13:00 午餐提醒："午餐吃了什么？发张照片我帮你算 🍱"
21:00 每日总结：自动聚合 → 推送当日报告
```

---

## 五、暗坑警告（从 3 个项目提取的 UNSAID）

| 暗坑 | 来源 | Skill 中的防护 |
|------|------|--------------|
| AI 估算不稳定，"一碗饭"可能估成 150-300g | ai-calorie-counter | 每次记录后展示数值，允许用户一键修正 |
| 中文食物 AI 识别准确率可能低于英文 | FoodYou CJK 暗坑 | V1 优先支持文字描述，照片识别标注"仅供参考" |
| 运动消耗因人而异，MET 值是平均值 | OpenNutriTracker | 明确标注"估算值" |
| 用户修改体重后历史数据应保持原样 | OpenNutriTracker TrackedDay | 每日日志开头记录当日目标快照 |
| "大约 500 卡"的快速记录不应和精确记录混算精度 | FoodYou ManualDiaryEntry | 快速记录标注"手动估计" |

---

## 六、与 Doramagic 产品旅程的对照

这次模拟走通了完整的用户旅程一：

| Phase | V5 定义 | 本次模拟 |
|-------|---------|---------|
| Phase 1 需求挖掘 | 用户说出模糊烦恼 | ✅ "我想要做一个记录食物卡路里的 skill" |
| Phase 2 发现作业 | 搜索+推荐 | ✅ 找到 3 个开源项目 + 4 个社区 skill + 1 个教程 |
| Phase 3 提取灵魂 | 提取知识 | ✅ 4 路并行灵魂提取 |
| Phase 4 锻造道具 | 组装定制 skill | ✅ 公约数提取 + 独创知识组装 → Skill 设计方案 |
| Phase 5 交付验证 | 交付给用户 | ⚠️ 设计方案已完成，未实际编写 SKILL.md |

**缺失的最后一步**：把上述设计方案编译成一份可运行的 SKILL.md，让 OpenClaw agent 能直接执行。

---

## 七、一句话总结

> 3 个项目的灵魂 + 4 个社区 skill + 1 个教程 = 1 个定制的食物卡路里追踪 Skill。不是从零设计，是站在 8 个前人的肩膀上组装。这就是 Doramagic 的价值——**把 8 份作业的精华，缝合成你的道具。**
