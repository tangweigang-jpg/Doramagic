#!/usr/bin/env python3
"""Generate knowledge type heatmap for 9 extracted projects - English labels."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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

knowledge_types = ["WHAT", "HOW", "IF/RULES", "WHY", "UNSAID", "STRUCTURE"]

data = np.array(
    [
        [8, 7, 5, 3, 2, 4],  # python-dotenv
        [6, 6, 9, 10, 6, 5],  # superpowers
        [8, 8, 6, 5, 5, 8],  # wger
        [7, 6, 8, 8, 5, 6],  # geo-seo-claude
        [6, 5, 7, 6, 4, 3],  # marketingskills
        [7, 7, 8, 7, 6, 7],  # claude-seo
        [7, 7, 8, 6, 5, 7],  # 30x-seo
        [6, 8, 9, 10, 6, 7],  # gstack
        [9, 9, 10, 8, 9, 9],  # OpenClaw
    ]
)

categories = {
    "Python Lib": ([0], "#3498db"),
    "AI Agent Eng": ([1, 7, 8], "#e74c3c"),
    "Web App": ([2], "#2ecc71"),
    "SEO/GEO": ([3, 4, 5, 6], "#f39c12"),
}

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [3, 1.2]})
fig.suptitle(
    "Doramagic Soul Extraction: Knowledge Density Heatmap (9 Projects)",
    fontsize=14,
    fontweight="bold",
    y=0.98,
)

# Main heatmap
im = ax1.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)

ax1.set_xticks(range(len(knowledge_types)))
ax1.set_xticklabels(knowledge_types, fontsize=10, fontweight="bold")
ax1.set_yticks(range(len(projects)))
ax1.set_yticklabels(projects, fontsize=10)

for i in range(len(projects)):
    for j in range(len(knowledge_types)):
        val = data[i, j]
        color = "white" if val < 4 or val > 8 else "black"
        ax1.text(
            j, i, str(val), ha="center", va="center", fontsize=12, fontweight="bold", color=color
        )

# Category color bars
for cat_name, (indices, color) in categories.items():
    for idx in indices:
        ax1.add_patch(
            plt.Rectangle(
                (-0.8, idx - 0.4), 0.3, 0.8, facecolor=color, edgecolor="none", clip_on=False
            )
        )

legend_elements = [
    plt.Rectangle((0, 0), 1, 1, facecolor=c, label=n) for n, (_, c) in categories.items()
]
ax1.legend(handles=legend_elements, loc="lower left", fontsize=9, framealpha=0.9)

ax1.set_title("Knowledge Type x Project Matrix", fontsize=11, pad=10)

cbar = plt.colorbar(im, ax=ax1, shrink=0.8, pad=0.02)
cbar.set_label("Knowledge Density (0-10)", fontsize=9)

# Right subplot: average by category
x = np.arange(len(knowledge_types))
width = 0.18
for i, (cat_name, (indices, color)) in enumerate(categories.items()):
    avg = data[indices].mean(axis=0)
    ax2.barh(x + i * width - 0.27, avg, width, label=cat_name, color=color, alpha=0.85)

ax2.set_yticks(x)
ax2.set_yticklabels(knowledge_types, fontsize=10)
ax2.set_xlim(0, 10)
ax2.set_xlabel("Avg Density", fontsize=10)
ax2.set_title("Average by Domain", fontsize=11, pad=10)
ax2.legend(fontsize=7, loc="lower right")
ax2.grid(axis="x", alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.95])

output_path = "/Users/tang/Documents/vibecoding/Doramagic/research/heatmap-9-projects.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Heatmap saved: {output_path}")
