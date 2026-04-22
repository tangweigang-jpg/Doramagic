#!/usr/bin/env python3
"""Generate PDF for Calorie Skill Assembly Report."""

import os

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

pdfmetrics.registerFont(
    TTFont("STHeiti", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0)
)
pdfmetrics.registerFont(
    TTFont("STHeitiLight", "/System/Library/Fonts/STHeiti Light.ttc", subfontIndex=0)
)

OUTPUT = "/Users/tang/Documents/vibecoding/Doramagic/research/calorie-skill-assembly.pdf"

DARK = HexColor("#1a1a2e")
ACCENT = HexColor("#16213e")
BLUE = HexColor("#0f3460")
HIGHLIGHT = HexColor("#e94560")
LIGHT_BG = HexColor("#f5f5f5")
BORDER = HexColor("#cccccc")
GREEN = HexColor("#27ae60")

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "T",
    parent=styles["Title"],
    fontName="STHeiti",
    fontSize=22,
    leading=28,
    textColor=DARK,
    spaceAfter=4 * mm,
    alignment=TA_CENTER,
)
subtitle_style = ParagraphStyle(
    "Sub",
    parent=styles["Normal"],
    fontName="STHeitiLight",
    fontSize=11,
    leading=15,
    textColor=HexColor("#666"),
    alignment=TA_CENTER,
    spaceAfter=6 * mm,
)
h1 = ParagraphStyle(
    "H1",
    parent=styles["Heading1"],
    fontName="STHeiti",
    fontSize=16,
    leading=22,
    textColor=DARK,
    spaceBefore=10 * mm,
    spaceAfter=4 * mm,
)
h2 = ParagraphStyle(
    "H2",
    parent=styles["Heading2"],
    fontName="STHeiti",
    fontSize=13,
    leading=18,
    textColor=BLUE,
    spaceBefore=6 * mm,
    spaceAfter=3 * mm,
)
h3 = ParagraphStyle(
    "H3",
    parent=styles["Heading3"],
    fontName="STHeiti",
    fontSize=11,
    leading=15,
    textColor=ACCENT,
    spaceBefore=4 * mm,
    spaceAfter=2 * mm,
)
body = ParagraphStyle(
    "B",
    parent=styles["Normal"],
    fontName="STHeitiLight",
    fontSize=9.5,
    leading=14,
    textColor=black,
    spaceAfter=2 * mm,
    alignment=TA_JUSTIFY,
)
bold = ParagraphStyle("Bd", parent=body, fontName="STHeiti")
quote = ParagraphStyle(
    "Q",
    parent=body,
    leftIndent=8 * mm,
    rightIndent=5 * mm,
    textColor=HexColor("#444"),
    borderColor=HIGHLIGHT,
    borderWidth=2,
    borderPadding=4,
    spaceAfter=3 * mm,
)
bullet = ParagraphStyle(
    "Bu", parent=body, leftIndent=8 * mm, bulletIndent=3 * mm, spaceAfter=1.5 * mm
)
code = ParagraphStyle(
    "Co",
    parent=body,
    fontName="Courier",
    fontSize=8,
    leading=11,
    leftIndent=5 * mm,
    backColor=LIGHT_BG,
    borderColor=BORDER,
    borderWidth=0.5,
    borderPadding=3,
    spaceAfter=3 * mm,
)


def B(t):
    return f"<b>{t}</b>"


def C(t):
    return f'<font face="Courier" size="8" color="#c0392b">{t}</font>'


def tbl(headers, rows, widths=None):
    data = [headers] + rows
    if not widths:
        widths = [165 * mm / len(headers)] * len(headers)
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "STHeiti"),
                ("FONTNAME", (0, 1), (-1, -1), "STHeitiLight"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def hr():
    return HRFlowable(
        width="100%", thickness=0.5, color=BORDER, spaceAfter=3 * mm, spaceBefore=1 * mm
    )


def build():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Doramagic: Calorie Skill Assembly",
        author="Doramagic",
    )
    s = []

    # Title page
    s.append(Spacer(1, 35 * mm))
    s.append(
        Paragraph("Doramagic", ParagraphStyle("Big", parent=title_style, fontSize=32, leading=40))
    )
    s.append(Spacer(1, 3 * mm))
    s.append(Paragraph("食物卡路里追踪 Skill 组装报告", title_style))
    s.append(Spacer(1, 10 * mm))
    s.append(Paragraph("极限模拟：3 个开源项目 + 4 个社区 Skill + 1 个教程", subtitle_style))
    s.append(Paragraph("2026-03-17", subtitle_style))
    s.append(Spacer(1, 20 * mm))
    s.append(
        Paragraph(
            "把 8 份作业的精华，缝合成你的道具。<br/>这就是 Doramagic 的价值。",
            ParagraphStyle("Tag", parent=quote, alignment=TA_CENTER, fontSize=11, leading=16),
        )
    )
    s.append(PageBreak())

    # Section 1: Sources
    s.append(Paragraph("一、知识来源", h1))
    s.append(hr())
    s.append(
        tbl(
            ["来源", "类型", "贡献重点"],
            [
                [
                    "ai-calorie-counter",
                    "开源项目",
                    "AI 拍照/文字→JSON 契约、BMR 计算、上下文动态注入",
                ],
                ["FoodYou", "开源项目", "42 字段营养素 schema、4 数据库来源、食谱系统、空值语义"],
                ["OpenNutriTracker", "开源项目", "IOM2005 TDEE 公式、运动 MET 值库、双数据库搜索"],
                ["ClawHub 4 个 skill", "社区", "存储路径标准、三餐提醒 cron、日/周/月查询"],
                ["LobsterLair", "教程", "视觉模型架构、人格层、Apple Health 集成"],
            ],
            [40 * mm, 25 * mm, 100 * mm],
        )
    )

    # Section 2: Consensus
    s.append(Paragraph("二、公约数（5 条共识知识）", h1))
    s.append(hr())
    consensus = [
        (
            "AI 估算 + 数据库查询双轨",
            "AI 先估算（快但不精确 80-90%），用户可选数据库校准（慢但精确）。两者互补不互斥。",
        ),
        (
            "IOM 2005 TDEE 公式",
            "最精确的每日热量需求计算，含性别细分体力活动系数。Mifflin-St Jeor 作备选。",
        ),
        (
            "每日 Markdown 日志",
            "OpenClaw 生态标准：~/clawd/memory/health/meals/YYYY-MM-DD.md。不需要数据库。",
        ),
        ("早/午/晚/零食 4 餐次", "行业标准分类。社区已验证三餐提醒时间：8AM / 1PM / 7PM。"),
        ("运动消耗纳入热量平衡", "MET × 体重 × 时长。内置 80+ 种运动 MET 值可直接复用。"),
    ]
    for i, (title, desc) in enumerate(consensus, 1):
        s.append(Paragraph(f"{B(f'共识 {i}：{title}')}", bold))
        s.append(Paragraph(desc, bullet))
        s.append(Spacer(1, 1 * mm))

    # Section 3: Unique Knowledge
    s.append(Paragraph("三、独创知识借鉴", h1))
    s.append(hr())
    s.append(
        tbl(
            ["来源", "独创知识", "为什么好"],
            [
                ["ai-calorie-counter", "消息即数据容器", "聊天记录=追踪日志，完美契合 OpenClaw"],
                ["ai-calorie-counter", "AI 输出 JSON 契约", "代码说事实，AI 说故事"],
                ["ai-calorie-counter", "聚合数据注入上下文", "省 token，建议更精准"],
                ["FoodYou", '"不知道吃什么，只知道大约多少卡"', "降低门槛，减少放弃率"],
                ["FoodYou", "CJK 搜索需专项处理", "中文用户关键暗坑"],
                ["OpenNutriTracker", "每日目标快照", "改设置不影响历史记录"],
                ["OpenNutriTracker", "80+ 种运动 MET 值", "直接复用"],
                ["LobsterLair", "人格层（鼓励型/毒舌型）", "OpenClaw 天然支持"],
            ],
            [35 * mm, 55 * mm, 75 * mm],
        )
    )

    s.append(PageBreak())

    # Section 4: Skill Design
    s.append(Paragraph("四、Skill 设计方案", h1))
    s.append(hr())

    s.append(Paragraph("4.1 定位", h2))
    s.append(
        Paragraph(
            "拍照或说一句话记录你吃了什么，AI 自动算卡路里，每天告诉你还能吃多少。轻量级 AI 助手，不是 42 字段营养学 App。",
            quote,
        )
    )

    s.append(Paragraph("4.2 核心功能（V1）", h2))
    s.append(
        tbl(
            ["功能", "触发方式", "背后逻辑"],
            [
                ["记录食物", '发照片 / "我吃了一碗面"', "AI 视觉/文字 → JSON → 写入当日日志"],
                ["记录运动", '"跑步 30 分钟"', "AI 识别 → MET × 体重 × 时长 → 写入日志"],
                ["查余量", '"我还能吃多少"', "TDEE - 已摄入 + 运动消耗 → 返回剩余"],
                ["快速记录", '"大约 500 卡"', "不查库直接记录（ManualDiaryEntry）"],
                ["每日总结", '晚 9 点自动 / "今天总结"', "聚合当日数据 → 与目标对比 → 评价"],
                ["历史查看", '"上周吃了什么"', "读取对应日期日志 → 聚合返回"],
            ],
            [25 * mm, 45 * mm, 95 * mm],
        )
    )

    s.append(Paragraph("4.3 用户引导（首次使用）", h2))
    s.append(Paragraph("收集：性别 → 年龄 → 身高体重 → 活动水平 → 目标（减重/维持/增重）", body))
    s.append(
        Paragraph(
            "计算 IOM 2005 TDEE → 展示每日目标（如 1800 kcal，蛋白质 90g / 碳水 225g / 脂肪 60g）",
            body,
        )
    )
    s.append(Paragraph('"随时发食物照片或告诉我你吃了什么，我来帮你记！"', body))

    s.append(Paragraph("4.4 数据存储", h2))
    s.append(
        Paragraph(
            f"{C('~/clawd/memory/health/profile.md')} — 用户档案<br/>"
            f"{C('~/clawd/memory/health/meals/YYYY-MM-DD.md')} — 每日食物日志<br/>"
            f"{C('~/clawd/memory/health/summary/weekly-YYYY-WNN.md')} — 周报",
            code,
        )
    )

    s.append(Paragraph("4.5 每日日志格式示例", h2))
    log_example = (
        "# 2026-03-17 食物日志<br/><br/>"
        "## 目标<br/>"
        "TDEE: 1800 kcal | 蛋白质: 90g | 碳水: 225g | 脂肪: 60g<br/><br/>"
        "## 早餐<br/>"
        "08:15 | 全麦面包 2 片 | 180 kcal | P:8g C:30g F:3g<br/>"
        "08:15 | 煎蛋 1 个 | 90 kcal | P:6g C:1g F:7g<br/><br/>"
        "## 午餐<br/>"
        "12:30 | 牛肉面一碗 | 550 kcal | P:25g C:65g F:18g<br/><br/>"
        "## 运动<br/>"
        "18:00 | 跑步 30 分钟 | -280 kcal<br/><br/>"
        "## 今日汇总<br/>"
        "已摄入: 915 kcal | 运动消耗: 280 kcal | 净摄入: 635 kcal | 剩余: 1165 kcal"
    )
    s.append(Paragraph(log_example, code))

    s.append(Paragraph("4.6 AI Prompt 契约", h2))
    s.append(Paragraph("AI 返回结构化 JSON（从 ai-calorie-counter 提取的核心模式）：", body))
    s.append(
        Paragraph(
            "food: {type, time, meal, name, weight, calories, protein, carbs, fat}<br/>"
            "activity: {type, time, name, duration, caloriesBurned}<br/>"
            "建议时注入聚合摘要（非全部记录）：已摄入总量 + TDEE + 运动消耗",
            code,
        )
    )

    s.append(Paragraph("4.7 人格配置 + 提醒", h2))
    s.append(Paragraph("• SOUL.md 配置人格（温暖鼓励型 / 毒舌型），从 LobsterLair 借鉴", bullet))
    s.append(Paragraph("• 三餐提醒 cron：8AM 早餐 / 1PM 午餐 / 9PM 每日总结", bullet))
    s.append(Paragraph("• 连续记录 7 天给成就感提示", bullet))

    s.append(PageBreak())

    # Section 5: Pitfalls
    s.append(Paragraph("五、暗坑防护（从 3 个项目提取）", h1))
    s.append(hr())
    s.append(
        tbl(
            ["暗坑", "来源", "防护措施"],
            [
                [
                    "AI 估算不稳定（150-300g 波动）",
                    "ai-calorie-counter",
                    "每次展示数值，允许一键修正",
                ],
                ["中文食物识别准确率低", "FoodYou CJK 暗坑", 'V1 优先文字，照片标"仅供参考"'],
                ["运动消耗因人而异", "OpenNutriTracker", '标注"估算值"'],
                ["改体重后历史数据失真", "OpenNutriTracker", "每日日志开头快照当日目标"],
                ["快速记录精度混淆", "FoodYou", '标注"手动估计"'],
            ],
            [45 * mm, 40 * mm, 80 * mm],
        )
    )

    # Section 6: Journey Mapping
    s.append(Paragraph("六、用户旅程对照", h1))
    s.append(hr())
    s.append(
        tbl(
            ["Phase", "V5 定义", "本次模拟"],
            [
                ["Phase 1", "需求挖掘", '✅ "我想做一个记录食物卡路里的 skill"'],
                ["Phase 2", "发现作业", "✅ 3 个开源项目 + 4 个社区 skill + 1 个教程"],
                ["Phase 3", "提取灵魂", "✅ 4 路 Sonnet 并行灵魂提取"],
                ["Phase 4", "锻造道具", "✅ 公约数 + 独创知识 → Skill 设计方案"],
                ["Phase 5", "交付验证", "⚠️ 设计方案完成，待编译为 SKILL.md"],
            ],
            [25 * mm, 35 * mm, 105 * mm],
        )
    )

    s.append(Spacer(1, 10 * mm))
    s.append(
        Paragraph(
            "3 个项目的灵魂 + 4 个社区 skill + 1 个教程<br/>= 1 个定制的食物卡路里追踪 Skill<br/><br/>"
            "不是从零设计，是站在 8 个前人的肩膀上组装。",
            ParagraphStyle("Final", parent=quote, alignment=TA_CENTER, fontSize=11, leading=16),
        )
    )

    doc.build(s)
    print(f"PDF: {OUTPUT} ({os.path.getsize(OUTPUT) // 1024} KB)")


if __name__ == "__main__":
    build()
