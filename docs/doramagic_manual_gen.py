#!/usr/bin/env python3
"""Generate Doramagic user introduction manual as PDF."""

from fpdf import FPDF
import os
from datetime import date

# Font paths
FONT_SONGTI = "/System/Library/Fonts/Supplemental/Songti.ttc"
FONT_HEITI = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_HIRAGINO = "/System/Library/Fonts/Hiragino Sans GB.ttc"

OUTPUT_PATH = os.path.expanduser("~/Doramagic_用户手册.pdf")


class DoramagicManual(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        # Register fonts
        self.add_font("Songti", "", FONT_SONGTI)
        self.add_font("Heiti", "", FONT_HEITI)
        self.add_font("Hiragino", "", FONT_HIRAGINO)

    def header(self):
        if self.page_no() == 1:
            return  # Cover page has no header
        self.set_font("Heiti", size=8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 8, "Doramagic 用户手册", align="L")
        self.cell(0, 8, f"v1.0  |  {date.today().strftime('%Y-%m-%d')}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-20)
        self.set_font("Heiti", size=8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"— {self.page_no()} —", align="C")

    def cover_page(self):
        self.add_page()
        self.ln(50)
        # Title
        self.set_font("Heiti", size=36)
        self.set_text_color(30, 30, 30)
        self.cell(0, 20, "Doramagic", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Songti", size=18)
        self.set_text_color(80, 80, 80)
        self.cell(0, 12, "开源项目灵魂提取系统", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_font("Songti", size=13)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "用户手册  v1.0", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(30)
        # Tagline
        self.set_font("Songti", size=14)
        self.set_text_color(60, 60, 60)
        self.cell(0, 10, "「不教用户做事，给他工具。」", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Songti", size=11)
        self.set_text_color(140, 140, 140)
        self.cell(0, 8, "灵感来自哆啦A梦：从口袋里掏出道具，让你自己解决问题。", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(40)
        # Date
        self.set_font("Songti", size=10)
        self.set_text_color(160, 160, 160)
        self.cell(0, 8, date.today().strftime("%Y 年 %m 月"), align="C", new_x="LMARGIN", new_y="NEXT")

    def section_title(self, num, title):
        self.ln(6)
        self.set_font("Heiti", size=18)
        self.set_text_color(30, 30, 30)
        self.cell(0, 14, f"{num}  {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(60, 60, 60)
        self.line(10, self.get_y(), 100, self.get_y())
        self.ln(6)

    def sub_title(self, title):
        self.ln(3)
        self.set_font("Heiti", size=13)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Songti", size=10.5)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Hiragino", size=10.5)
        self.set_text_color(40, 40, 40)
        self.cell(6, 6.5, "·")
        self.set_font("Songti", size=10.5)
        self.multi_cell(0, 6.5, text)
        self.ln(1)

    def code_block(self, text):
        self.set_fill_color(245, 245, 245)
        self.set_font("Hiragino", size=9)
        self.set_text_color(50, 50, 50)
        x = self.get_x()
        w = self.w - self.l_margin - self.r_margin
        # Calculate height needed
        lines = text.split("\n")
        h = len(lines) * 5.5 + 6
        self.rect(x, self.get_y(), w, h, "F")
        self.ln(3)
        for line in lines:
            self.cell(4)
            self.cell(0, 5.5, line, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def table_row(self, cells, widths, is_header=False):
        if is_header:
            self.set_font("Heiti", size=9.5)
            self.set_fill_color(240, 240, 240)
            self.set_text_color(30, 30, 30)
        else:
            self.set_font("Songti", size=9.5)
            self.set_fill_color(255, 255, 255)
            self.set_text_color(50, 50, 50)
        h = 8
        for i, (cell, w) in enumerate(zip(cells, widths)):
            self.cell(w, h, cell, border=1, fill=True, align="L" if i == 0 else "C")
        self.ln(h)

    def highlight_box(self, text):
        self.set_fill_color(255, 250, 235)
        self.set_draw_color(220, 190, 100)
        w = self.w - self.l_margin - self.r_margin
        self.set_font("Songti", size=10.5)
        self.set_text_color(80, 60, 0)
        # Calculate lines
        lines = self.multi_cell(w - 10, 6.5, text, dry_run=True, output="LINES")
        h = len(lines) * 6.5 + 10
        y = self.get_y()
        self.rect(self.l_margin, y, w, h, "DF")
        self.set_xy(self.l_margin + 5, y + 5)
        self.multi_cell(w - 10, 6.5, text)
        self.ln(4)


def build_manual():
    pdf = DoramagicManual()

    # ===== Cover =====
    pdf.cover_page()

    # ===== TOC =====
    pdf.add_page()
    pdf.set_font("Heiti", size=20)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 16, "目录", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    toc_items = [
        ("01", "Doramagic 是什么"),
        ("02", "它能帮你解决什么问题"),
        ("03", "核心理念：双半魂模型"),
        ("04", "谁适合使用 Doramagic"),
        ("05", "产品形态"),
        ("06", "快速上手"),
        ("07", "使用提取结果"),
        ("08", "知识体系详解"),
        ("09", "质量保障"),
        ("10", "常见问题"),
    ]
    for num, title in toc_items:
        pdf.set_font("Songti", size=11)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(12, 9, num)
        pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")

    # ===== Section 1 =====
    pdf.add_page()
    pdf.section_title("01", "Doramagic 是什么")

    pdf.body_text(
        "Doramagic 是一个开源项目「灵魂提取」系统。它从开源项目的代码、文档和社区经验中，"
        "提取出隐藏在表面之下的深层知识——设计哲学、决策规则、社区踩坑经验——然后将这些知识"
        "转化为结构化的 AI 知识包，注入到 AI 助手中，使其成为该项目的专家级顾问。"
    )

    pdf.body_text(
        "简单来说：你给 Doramagic 一个开源项目的地址，它帮你把这个项目的「灵魂」提取出来，"
        "装进 AI 的脑袋里。从此，AI 不再是泛泛而谈的通才，而是深谙该项目设计哲学、"
        "了解社区踩坑经验的专家顾问。"
    )

    pdf.highlight_box(
        "核心数据：通用 AI 对开源项目的回答准确率约 42%，经常「自信地给出错误答案」。"
        "注入 Doramagic 提取的灵魂后，准确率提升至 96%，幻觉完全消除。"
    )

    pdf.sub_title("名字的由来")
    pdf.body_text(
        "Doramagic = Doraemon + Magic。灵感来自哆啦A梦：哆啦A梦从不教大雄怎么做事，"
        "而是从百宝袋里掏出道具让大雄自己解决问题。Doramagic 也一样——我们不教你怎么用开源项目，"
        "而是给你一个装满了该项目知识的 AI 顾问，让你自己去探索和解决问题。"
    )

    # ===== Section 2 =====
    pdf.add_page()
    pdf.section_title("02", "它能帮你解决什么问题")

    pdf.sub_title("问题一：AI 对开源项目一知半解")
    pdf.body_text(
        "你有没有过这样的经历？问 AI 关于某个开源项目的问题，AI 回答得头头是道，"
        "但实际一试却发现答案是错的。这不是 AI「笨」，而是它确实不了解这个项目的深层设计，"
        "只能根据表面信息猜测。Doramagic 把项目的深层知识注入 AI，让它真正「懂」这个项目。"
    )

    pdf.sub_title("问题二：开源知识散落各处")
    pdf.body_text(
        "一个开源项目的知识散落在代码、README、Issue、Discussion、Stack Overflow、博客等"
        "无数角落。想要全面了解一个项目，你需要花大量时间翻阅这些资料。"
        "Doramagic 自动从所有这些来源统一提取、结构化、质量验证后输出。"
    )

    pdf.sub_title("问题三：没有技术团队也想用开源项目")
    pdf.body_text(
        "99% 的中小企业没有专职技术团队，无法阅读源码、理解架构、追踪 Issue。"
        "Doramagic 将项目知识转化为自然语言的 AI 顾问服务，"
        "非技术用户也能通过对话了解项目的能力、限制和最佳实践。"
    )

    pdf.sub_title("问题四：「差不多正确」的陷阱")
    pdf.body_text(
        "AI 看似合理实则微妙错误的回答，对非技术用户来说几乎无法辨别。"
        "Doramagic 提取的每一条知识都带有证据溯源（代码行号、Issue 编号、社区讨论链接），"
        "还有置信度标注，帮你判断哪些信息是确凿的、哪些是推测性的。"
    )

    # ===== Section 3 =====
    pdf.add_page()
    pdf.section_title("03", "核心理念：双半魂模型")

    pdf.body_text(
        "Doramagic 认为，一个开源项目的完整「灵魂」由两个互补的半魂组成："
    )

    pdf.sub_title("代码半魂 (Code Soul)")
    pdf.body_text(
        "从源代码中提取的知识：设计哲学、心智模型、架构意图、决策规则、模块边界。"
        "它回答的核心问题是——「这个项目是怎么工作的，以及为什么这样设计」。"
    )

    pdf.sub_title("社区半魂 (Community Soul)")
    pdf.body_text(
        "从 GitHub Issues、Discussions、PR 评论中提取的实践经验：真实的坑、"
        "兼容性问题、部署经验、社区最佳实践、版本演化故事。"
        "它回答的核心问题是——「实际使用中会遇到什么事」。"
    )

    pdf.highlight_box(
        "效果对比：\n"
        "仅代码半魂：准确率从 42% 提升至 83%（+96%）\n"
        "完整双半魂：准确率从 42% 提升至 96%（+125%）\n"
        "社区半魂贡献了额外 13% 的准确率提升，是消除最后一批幻觉的关键。"
    )

    pdf.sub_title("知识层次：WHAT / HOW / WHY / UNSAID")
    pdf.body_text("Doramagic 提取的知识分为四个层次：")
    pdf.bullet("WHAT / HOW / IF — 可以直接从代码中读取的事实性知识（确定性提取）")
    pdf.bullet("WHY — 设计哲学和心智模型，需要深度推理才能发现（最高价值）")
    pdf.bullet("UNSAID — 文档中从不提及、只有社区老手才知道的隐性知识（独有价值）")

    pdf.body_text(
        "市面上的代码分析工具只能提取 WHAT 和 HOW 层。"
        "Doramagic 的核心护城河在于 WHY 和 UNSAID 层的提取能力——这是行业空白。"
    )

    # ===== Section 4 =====
    pdf.add_page()
    pdf.section_title("04", "谁适合使用 Doramagic")

    pdf.sub_title("技术决策者 (CTO / 技术负责人)")
    pdf.bullet("快速评估开源项目的设计理念和技术风险")
    pdf.bullet("了解社区踩坑经验来做技术选型决策")
    pdf.bullet("典型场景：评估是否采用某个开源框架")

    pdf.sub_title("开发者 (个人 / 团队)")
    pdf.bullet("快速上手新项目的代码架构和设计哲学")
    pdf.bullet("让 AI 编码助手提供项目特定的精准建议")
    pdf.bullet("典型场景：将提取的知识加载到 Claude Code / Cursor IDE 中辅助开发")

    pdf.sub_title("非技术创业者 / 产品经理")
    pdf.bullet("没有技术团队但需要利用开源项目的知识")
    pdf.bullet("通过 AI 顾问了解项目能做什么、有什么限制")
    pdf.bullet("典型场景：通过 AI 顾问了解开源 CRM 的定制能力和部署要求")

    pdf.sub_title("运维工程师")
    pdf.bullet("快速获取项目的部署经验和常见问题清单")
    pdf.bullet("了解社区中已知的兼容性问题和解决方案")
    pdf.bullet("典型场景：部署前获取完整的踩坑清单")

    # ===== Section 5 =====
    pdf.add_page()
    pdf.section_title("05", "产品形态")

    pdf.body_text("Doramagic 以两种形态交付，共享相同的提取引擎和知识体系：")

    pdf.sub_title("形态一：命令行工具 (CLI)")
    pdf.body_text(
        "独立的命令行工具，安装后即可在终端中使用。适合开发者和技术用户，"
        "支持 macOS 和 Linux 系统。"
    )
    pdf.code_block(
        "doramagic full https://github.com/user/project\n"
        "doramagic extract /path/to/local/project\n"
        "doramagic community https://github.com/user/project"
    )

    pdf.sub_title("形态二：OpenClaw Skill")
    pdf.body_text(
        "作为 OpenClaw 平台的原生技能运行。用户通过自然语言对话触发，"
        "无需记忆命令语法。适合所有用户，包括非技术背景的使用者。"
    )
    pdf.code_block(
        '用户：帮我提取 python-dotenv 项目的灵魂\n'
        '用户：/dora https://github.com/user/project\n'
        '用户：这个项目有什么坑？https://github.com/user/project'
    )

    pdf.sub_title("模型无关设计")
    pdf.body_text(
        "Doramagic 不绑定任何特定 AI 模型。它通过「能力路由」机制，"
        "根据任务需求自动选择最合适的模型。"
        "目前支持 Claude (Anthropic)、Gemini (Google)、GPT (OpenAI)、MiniMax，"
        "以及通过 Ollama 运行的本地开源模型。你可以完全离线使用。"
    )

    # ===== Section 6 =====
    pdf.add_page()
    pdf.section_title("06", "快速上手")

    pdf.sub_title("第一步：安装")
    pdf.code_block(
        "# 克隆项目\n"
        "git clone https://github.com/user/doramagic.git\n"
        "cd doramagic\n"
        "\n"
        "# 安装依赖\n"
        "pip install pydantic\n"
        "\n"
        "# 配置模型（编辑 models.json，填入你的 API Key）\n"
        "cp models.json.example models.json"
    )

    pdf.sub_title("第二步：运行第一次提取")
    pdf.code_block(
        "# 对一个 GitHub 项目执行完整灵魂提取\n"
        "doramagic full https://github.com/theskumar/python-dotenv\n"
        "\n"
        "# 或者提取本地项目\n"
        "doramagic full /path/to/your/project"
    )

    pdf.sub_title("提取过程示意")
    pdf.body_text("执行后你会看到类似这样的进度输出：")
    pdf.code_block(
        "Preparing repository...\n"
        "  Repository prepared (1,105 lines, 23 files)\n"
        "Running Eagle Eye analysis...\n"
        "  Identity discovered: python-dotenv\n"
        "  Module map: 4 modules identified\n"
        "Running Deep Dive extraction...\n"
        "  Concept cards: 6 extracted\n"
        "  Workflow cards: 3 extracted\n"
        "  Decision rules: 8 extracted\n"
        "Running quality validation...\n"
        "  Quality gate: PASS (avg: 96)\n"
        "Extracting community wisdom...\n"
        "  Community rules: 21 extracted\n"
        "Assembling final output...\n"
        "  Output saved to ./doramagic-output/python-dotenv/"
    )

    pdf.sub_title("第三步：查看输出")
    pdf.body_text("提取完成后，输出目录包含以下文件：")
    pdf.bullet("CLAUDE.md — 注入 Claude Code 的知识文件")
    pdf.bullet(".cursorrules — 注入 Cursor IDE 的知识文件")
    pdf.bullet("advisor-brief.md — 面向非技术用户的顾问摘要")
    pdf.bullet("cards/ — 所有知识卡片（概念、工作流、决策规则等）")
    pdf.bullet("expert_narrative.md — 专家级项目叙事（约 1500 词）")
    pdf.bullet("module-map.md — 项目模块架构图")
    pdf.bullet("community-wisdom.md — 社区踩坑经验汇总")
    pdf.bullet("judge-report.md — 质量评估报告")

    # ===== Section 7 =====
    pdf.add_page()
    pdf.section_title("07", "使用提取结果")

    pdf.sub_title("场景一：注入 Claude Code")
    pdf.body_text(
        "将生成的 CLAUDE.md 复制到你的项目根目录。之后在项目中使用 Claude Code 时，"
        "AI 会自动加载这些知识，回答质量将大幅提升。"
    )
    pdf.code_block(
        "cp ./doramagic-output/python-dotenv/CLAUDE.md \\\n"
        "   /path/to/your/project/CLAUDE.md"
    )

    pdf.sub_title("场景二：注入 Cursor IDE")
    pdf.body_text(
        "将生成的 .cursorrules 复制到项目根目录。Cursor 会自动读取并应用这些规则，"
        "在编码建议中融入项目特定的设计哲学和最佳实践。"
    )
    pdf.code_block(
        "cp ./doramagic-output/python-dotenv/.cursorrules \\\n"
        "   /path/to/your/project/.cursorrules"
    )

    pdf.sub_title("场景三：作为 AI 顾问上下文")
    pdf.body_text(
        "advisor-brief.md 可以复制到任何 AI 对话中作为上下文。"
        "将它粘贴到 ChatGPT、Claude 或其他 AI 助手的对话中，"
        "AI 立即变成该项目的专家顾问。"
    )

    pdf.sub_title("场景四：团队知识共享")
    pdf.body_text(
        "将提取结果提交到团队的代码仓库中。新成员加入时，"
        "AI 助手自动拥有项目的深度知识，大幅缩短上手时间。"
        "知识卡片也可以作为团队文档的补充，记录那些「大家都知道但没人写下来」的隐性知识。"
    )

    # ===== Section 8 =====
    pdf.add_page()
    pdf.section_title("08", "知识体系详解")

    pdf.sub_title("五种知识卡片")
    pdf.body_text("Doramagic 将提取的知识组织为五种标准化卡片：")

    pdf.ln(2)
    widths = [36, 28, 68, 58]
    pdf.table_row(["类型", "ID 前缀", "用途", "示例"], widths, is_header=True)
    pdf.table_row(["概念卡片", "CC-", "核心概念的定义和边界", "「.env 文件的加载优先级」"], widths)
    pdf.table_row(["工作流卡片", "WC-", "关键流程的步骤说明", "「配置加载的完整流程」"], widths)
    pdf.table_row(["决策规则", "DR-", "条件判断和踩坑经验", "「生产环境不要用 load_dotenv()」"], widths)
    pdf.table_row(["合约卡片", "CT-", "系统不变量和约束", "「.env 文件必须是 UTF-8」"], widths)
    pdf.table_row(["架构卡片", "AC-", "系统架构全景图", "「模块依赖关系和数据流」"], widths)

    pdf.ln(4)
    pdf.sub_title("证据级别体系")
    pdf.body_text("每条提取的知识都标注了证据来源的可信度：")

    widths2 = [20, 36, 80, 54]
    pdf.table_row(["级别", "名称", "说明", "可信度"], widths2, is_header=True)
    pdf.table_row(["E1", "源代码", "直接从代码提取，有文件名和行号引用", "最高"], widths2)
    pdf.table_row(["E2", "维护者声明", "来自项目维护者的 Issue/PR 评论", "高"], widths2)
    pdf.table_row(["E3", "社区共识", "多个用户在讨论中达成的共识", "中"], widths2)
    pdf.table_row(["E4", "轶事证据", "个别用户报告或博客文章", "参考"], widths2)

    pdf.ln(4)
    pdf.sub_title("置信度系统")
    pdf.body_text("每条知识还经过证据链验证，给出四级置信度判定：")
    pdf.bullet("SUPPORTED — 有代码+文档双重证据支持，可信赖注入")
    pdf.bullet("CONTESTED — 仅有社区来源，标注为隐性知识 (UNSAID)")
    pdf.bullet("WEAK — 推理+旁证，标记为「推测」")
    pdf.bullet("REJECTED — 仅有推理无旁证，隔离排除，不进入输出")

    pdf.ln(2)
    pdf.sub_title("灵魂积木 (Bricks)")
    pdf.body_text(
        "Doramagic 内置 89 块「灵魂积木」，覆盖 12 个主流框架和领域"
        "（Python、Django、FastAPI、React、Go、Home Assistant 等以及"
        "金融、健康、PKM 等垂直领域）。"
        "积木是框架级的公共知识基线，在提取时自动注入，"
        "帮助提取引擎区分「项目特有的知识」和「框架通用的知识」，减少噪音。"
    )

    # ===== Section 9 =====
    pdf.add_page()
    pdf.section_title("09", "质量保障")

    pdf.body_text(
        "Doramagic 对提取质量的要求极为严格。每一次提取都经过多层验证，"
        "确保输出的知识是准确、可追溯、可操作的。"
    )

    pdf.sub_title("验证门控 (Stage 3.5)")
    pdf.body_text(
        "提取完成后，系统自动运行验证脚本，检查：结构完整性（所有必需卡片是否存在）、"
        "引用有效性（证据锚点是否指向真实文件和行号）、一致性（跨卡片引用是否矛盾）、"
        "完整性（是否满足最低数量要求）。"
        "验证不通过会自动修复并重试，最多重试两次。"
    )

    pdf.sub_title("五维评分系统")
    pdf.body_text("最终输出通过五个维度的综合评分：")
    pdf.bullet("忠实度 (Faithfulness) — 提取的知识是否与源代码一致")
    pdf.bullet("覆盖度 (Coverage) — 是否覆盖了项目的关键知识点")
    pdf.bullet("可追溯性 (Traceability) — 每条知识是否有证据来源")
    pdf.bullet("一致性 (Consistency) — 知识点之间是否存在矛盾")
    pdf.bullet("可操作性 (Actionability) — 知识是否具有实际指导价值")

    pdf.highlight_box(
        "最终判定标准：\n"
        "PASS — 0 个错误且均分 >= 80 分\n"
        "REVISE — <= 3 个错误且均分 >= 55 分（需修订后重新提取）\n"
        "FAIL — 不满足以上条件（需人工介入排查）"
    )

    pdf.sub_title("暗雷检测 (DSD)")
    pdf.body_text(
        "Doramagic 内置「欺骗性来源检测」系统 (Deceptive Source Detection)，"
        "通过 8 项确定性指标检查提取来源是否可信。"
        "这防止了 AI 从过时文档、误导性注释或废弃代码中提取错误知识。"
        "检测为 WARNING 级别，不会阻断流程，但会在输出中明确标注。"
    )

    # ===== Section 10 =====
    pdf.add_page()
    pdf.section_title("10", "常见问题")

    pdf.sub_title("Q: 支持哪些编程语言的项目？")
    pdf.body_text(
        "Doramagic 对任何编程语言的项目都可以提取。内置积木覆盖了 Python、Go、"
        "JavaScript/TypeScript (React)、Django、FastAPI/Flask 等主流技术栈，"
        "对这些语言的提取效果最佳。其他语言也可以提取，只是可能缺少框架基线知识。"
    )

    pdf.sub_title("Q: 提取一个项目需要多长时间？")
    pdf.body_text(
        "取决于项目规模和选择的 AI 模型。中等规模的项目（数千行代码）完整提取"
        "通常在几分钟内完成。大型项目可能需要更长时间。"
    )

    pdf.sub_title("Q: 可以完全离线使用吗？")
    pdf.body_text(
        "可以。配合 Ollama 使用本地模型即可实现完全离线运行，无需任何 API Key，"
        "代码和知识不会离开你的电脑。"
    )

    pdf.sub_title("Q: 提取结果的准确率如何保证？")
    pdf.body_text(
        "通过多层验证机制保证：确定性事实提取（不依赖 AI 的硬编码检查）作为校准基准、"
        "验证门控自动检查结构和引用、五维评分系统综合评估、"
        "暗雷检测过滤不可信来源、置信度标注让用户自行判断。"
    )

    pdf.sub_title("Q: 支持私有仓库吗？")
    pdf.body_text(
        "支持。你可以直接提取本地路径上的项目，无需将代码上传到任何外部服务。"
        "配合本地模型使用，整个过程完全在你的机器上完成。"
    )

    pdf.sub_title("Q: 提取结果会过时吗？")
    pdf.body_text(
        "会。开源项目持续演进，提取的知识是该时间点的快照。"
        "建议在项目发布重大版本更新后重新提取。"
        "Doramagic 的提取速度很快，重新提取的成本很低。"
    )

    pdf.sub_title("Q: 与 Copilot、Cursor 等工具是什么关系？")
    pdf.body_text(
        "Doramagic 不是 Copilot 或 Cursor 的替代品，而是它们的增强。"
        "Copilot/Cursor 提供编码补全能力，Doramagic 提供项目深度知识。"
        "将 Doramagic 提取的知识（CLAUDE.md / .cursorrules）加载到这些工具中，"
        "它们的建议质量会大幅提升。"
    )

    # ===== Back cover =====
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font("Heiti", size=16)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 12, "Doramagic", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Songti", size=11)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, "不教用户做事，给他工具。", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Songti", size=10)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 7, "代码说事实，AI 说故事。", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "能力升级，本质不变。", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "宁可漏报，不可误报。", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "冲突本身就是高价值知识。", align="C", new_x="LMARGIN", new_y="NEXT")

    # Save
    pdf.output(OUTPUT_PATH)
    print(f"PDF saved to: {OUTPUT_PATH}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_manual()
