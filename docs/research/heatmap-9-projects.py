#!/usr/bin/env python3
"""Generate knowledge type heatmap for 9 extracted projects."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# 9 projects × 6 knowledge types
# Scores: 0-10 (knowledge density estimate based on soul extraction)

projects = [
    "python-dotenv",
    "superpowers",
    "wger",
    "geo-seo-claude",
    "marketingskills",
    "claude-seo",
    "30x-seo",
    "gstack",
    "OpenClaw",
]

knowledge_types = [
    "WHAT\n概念",
    "HOW\n工作流",
    "IF\n规则",
    "WHY\n设计哲学",
    "UNSAID\n暗坑",
    "STRUCTURE\n架构",
]

# Data matrix: [project][knowledge_type]
# Estimated from actual extraction results and manual analysis
data = np.array(
    [
        # WHAT  HOW   IF    WHY   UNSAID  STRUCTURE
        [8, 7, 5, 3, 2, 4],  # python-dotenv (小库，概念清晰，WHY少)
        [6, 6, 9, 10, 6, 5],  # superpowers (方法论框架，WHY极高，IF高)
        [8, 8, 6, 5, 5, 8],  # wger (大应用，STRUCTURE高)
        [7, 6, 8, 8, 5, 6],  # geo-seo-claude (SEO领域知识丰富)
        [6, 5, 7, 6, 4, 3],  # marketingskills (广而浅)
        [7, 7, 8, 7, 6, 7],  # claude-seo (全栈SEO，均衡)
        [7, 7, 8, 6, 5, 7],  # 30x-seo (与claude-seo相似)
        [6, 8, 9, 10, 6, 7],  # gstack (方法论框架，WHY极高)
        [9, 9, 10, 8, 9, 9],  # OpenClaw (巨型平台，全面高)
    ]
)

# Project categories for color coding
categories = {
    "Python 工具库": [0],
    "AI Agent 工程": [1, 7, 8],
    "Web 应用": [2],
    "SEO/GEO": [3, 4, 5, 6],
}

cat_colors = {
    "Python 工具库": "#3498db",
    "AI Agent 工程": "#e74c3c",
    "Web 应用": "#2ecc71",
    "SEO/GEO": "#f39c12",
}

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8), gridspec_kw={"width_ratios": [3, 1]})
fig.suptitle("Doramagic 灵魂提取：9 个项目的知识密度热力图", fontsize=16, fontweight="bold", y=0.98)

# Heatmap
im = ax1.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)

# Labels
ax1.set_xticks(range(len(knowledge_types)))
ax1.set_xticklabels(knowledge_types, fontsize=10)
ax1.set_yticks(range(len(projects)))
ax1.set_yticklabels(projects, fontsize=10)

# Add text annotations
for i in range(len(projects)):
    for j in range(len(knowledge_types)):
        val = data[i, j]
        color = "white" if val < 4 or val > 8 else "black"
        ax1.text(
            j, i, str(val), ha="center", va="center", fontsize=11, fontweight="bold", color=color
        )

# Add category color bars on left
for cat_name, indices in categories.items():
    for idx in indices:
        ax1.add_patch(
            plt.Rectangle(
                (-0.8, idx - 0.4),
                0.3,
                0.8,
                facecolor=cat_colors[cat_name],
                edgecolor="none",
                clip_on=False,
            )
        )

# Category legend
legend_elements = [plt.Rectangle((0, 0), 1, 1, facecolor=c, label=n) for n, c in cat_colors.items()]
ax1.legend(handles=legend_elements, loc="lower left", fontsize=9, framealpha=0.9)

ax1.set_title("知识类型 × 项目矩阵", fontsize=12, pad=10)

# Colorbar
cbar = plt.colorbar(im, ax=ax1, shrink=0.8, pad=0.02)
cbar.set_label("知识密度 (0-10)", fontsize=10)

# Right subplot: summary radar-like bar chart
# Average by category
cat_avgs = {}
for cat_name, indices in categories.items():
    cat_avgs[cat_name] = data[indices].mean(axis=0)

x = np.arange(len(knowledge_types))
width = 0.18
for i, (cat_name, avg) in enumerate(cat_avgs.items()):
    ax2.barh(
        x + i * width - 0.27, avg, width, label=cat_name, color=cat_colors[cat_name], alpha=0.85
    )

ax2.set_yticks(x)
ax2.set_yticklabels(knowledge_types, fontsize=10)
ax2.set_xlim(0, 10)
ax2.set_xlabel("平均知识密度", fontsize=10)
ax2.set_title("按领域分类的平均密度", fontsize=12, pad=10)
ax2.legend(fontsize=8, loc="lower right")
ax2.grid(axis="x", alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.95])

output_path = "/Users/tang/Documents/vibecoding/Doramagic/research/heatmap-9-projects.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Heatmap saved: {output_path}")

# Also print key insights
print("\n=== Key Insights ===")
print(f"\nWHY 密度最高的项目: {projects[np.argmax(data[:, 3])]} ({data[:, 3].max()})")
print(f"UNSAID 密度最高的项目: {projects[np.argmax(data[:, 4])]} ({data[:, 4].max()})")
print(f"整体密度最高的项目: {projects[np.argmax(data.sum(axis=1))]} ({data.sum(axis=1).max()})")
print(f"整体密度最低的项目: {projects[np.argmin(data.sum(axis=1))]} ({data.sum(axis=1).min()})")

print("\n按知识类型的平均密度:")
for j, kt in enumerate(["WHAT", "HOW", "IF", "WHY", "UNSAID", "STRUCTURE"]):
    print(f"  {kt}: {data[:, j].mean():.1f}")

print("\n按领域的总密度:")
for cat_name, indices in categories.items():
    total = data[indices].sum() / len(indices)
    print(f"  {cat_name}: {total:.1f}")
