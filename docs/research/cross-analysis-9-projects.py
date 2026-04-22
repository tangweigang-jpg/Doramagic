#!/usr/bin/env python3
"""Cross-analysis of 9 projects: similarity matrix + knowledge gap + domain clustering."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# No scipy needed - using numpy directly

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

short_names = [
    "dotenv",
    "superpw",
    "wger",
    "geo-seo",
    "mktskill",
    "cl-seo",
    "30x-seo",
    "gstack",
    "OClaw",
]

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

knowledge_types = ["WHAT", "HOW", "IF", "WHY", "UNSAID", "STRUCT"]

fig, axes = plt.subplots(2, 2, figsize=(16, 14))
fig.suptitle("Doramagic: 9-Project Cross-Analysis", fontsize=15, fontweight="bold", y=0.98)

# === 1. Similarity Matrix (cosine similarity) ===
ax1 = axes[0, 0]
# Normalize rows for cosine sim
norms = np.linalg.norm(data, axis=1, keepdims=True)
normalized = data / norms
sim_matrix = normalized @ normalized.T

im1 = ax1.imshow(sim_matrix, cmap="Blues", vmin=0.85, vmax=1.0)
ax1.set_xticks(range(len(short_names)))
ax1.set_xticklabels(short_names, fontsize=8, rotation=45, ha="right")
ax1.set_yticks(range(len(short_names)))
ax1.set_yticklabels(short_names, fontsize=8)

for i in range(len(projects)):
    for j in range(len(projects)):
        val = sim_matrix[i, j]
        color = "white" if val > 0.97 else "black"
        ax1.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7, color=color)

ax1.set_title("1. Project Similarity Matrix (Cosine)", fontsize=11, pad=8)
plt.colorbar(im1, ax=ax1, shrink=0.8)

# === 2. Knowledge Gap Analysis (deviation from "ideal") ===
ax2 = axes[0, 1]
# "Ideal" = max observed per knowledge type
ideal = data.max(axis=0)
gaps = ideal - data  # higher = bigger gap

im2 = ax2.imshow(gaps, cmap="Reds", aspect="auto", vmin=0, vmax=8)
ax2.set_xticks(range(len(knowledge_types)))
ax2.set_xticklabels(knowledge_types, fontsize=10, fontweight="bold")
ax2.set_yticks(range(len(projects)))
ax2.set_yticklabels(projects, fontsize=9)

for i in range(len(projects)):
    for j in range(len(knowledge_types)):
        val = gaps[i, j]
        if val > 0:
            color = "white" if val > 5 else "black"
            ax2.text(
                j,
                i,
                f"-{int(val)}",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color=color,
            )

ax2.set_title("2. Knowledge Gaps (vs best-in-class)", fontsize=11, pad=8)
plt.colorbar(im2, ax=ax2, shrink=0.8)

# === 3. WHY vs UNSAID scatter ===
ax3 = axes[1, 0]
colors_map = {
    0: "#3498db",
    1: "#e74c3c",
    2: "#2ecc71",
    3: "#f39c12",
    4: "#f39c12",
    5: "#f39c12",
    6: "#f39c12",
    7: "#e74c3c",
    8: "#e74c3c",
}

for i, (name, short) in enumerate(zip(projects, short_names)):
    ax3.scatter(
        data[i, 3],
        data[i, 4],
        s=data[i].sum() * 8,
        c=colors_map[i],
        alpha=0.7,
        edgecolors="black",
        linewidth=0.5,
    )
    ax3.annotate(
        short, (data[i, 3], data[i, 4]), fontsize=8, xytext=(5, 5), textcoords="offset points"
    )

ax3.set_xlabel("WHY Density", fontsize=10)
ax3.set_ylabel("UNSAID Density", fontsize=10)
ax3.set_xlim(1, 11)
ax3.set_ylim(1, 10)
ax3.set_title("3. WHY vs UNSAID (bubble size = total density)", fontsize=11, pad=8)
ax3.grid(alpha=0.3)

# Quadrant labels
ax3.axhline(y=5.5, color="gray", linestyle="--", alpha=0.3)
ax3.axvline(x=6.5, color="gray", linestyle="--", alpha=0.3)
ax3.text(2, 9, "High UNSAID\nLow WHY", fontsize=7, ha="center", color="gray", style="italic")
ax3.text(9, 9, "HIGH VALUE\n(WHY+UNSAID)", fontsize=7, ha="center", color="red", fontweight="bold")
ax3.text(2, 2, "SIMPLE\nprojects", fontsize=7, ha="center", color="gray", style="italic")
ax3.text(9, 2, "High WHY\nLow UNSAID", fontsize=7, ha="center", color="gray", style="italic")

# === 4. Extraction ROI estimate ===
ax4 = axes[1, 1]

# ROI = (WHY + UNSAID potential) / project_size_estimate
size_estimate = np.array([2, 5, 12, 9, 55, 9, 11, 22, 140])  # approximate KLOC or MB
why_unsaid_potential = (10 - data[:, 3]) + (10 - data[:, 4])  # room for improvement
roi = why_unsaid_potential / np.log1p(size_estimate) * 3  # normalized

# Sort by ROI
roi_order = np.argsort(roi)[::-1]
y_pos = np.arange(len(projects))
bars = ax4.barh(
    y_pos,
    roi[roi_order],
    color=["#e74c3c" if roi[roi_order[i]] > 5 else "#3498db" for i in range(len(projects))],
    alpha=0.8,
)
ax4.set_yticks(y_pos)
ax4.set_yticklabels([projects[i] for i in roi_order], fontsize=9)
ax4.set_xlabel("Agentic Extraction ROI (WHY+UNSAID gap / log(size))", fontsize=9)
ax4.set_title("4. Where Agentic Extraction Adds Most Value", fontsize=11, pad=8)
ax4.grid(axis="x", alpha=0.3)

for i, v in enumerate(roi[roi_order]):
    ax4.text(v + 0.1, i, f"{v:.1f}", va="center", fontsize=8)

plt.tight_layout(rect=[0, 0, 1, 0.95])

output_path = "/Users/tang/Documents/vibecoding/Doramagic/research/cross-analysis-9-projects.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Saved: {output_path}")

# Print key insights
print("\n=== SIMILARITY INSIGHTS ===")
# Find most similar pairs (excluding diagonal)
sim_flat = []
for i in range(len(projects)):
    for j in range(i + 1, len(projects)):
        sim_flat.append((sim_matrix[i, j], projects[i], projects[j]))
sim_flat.sort(reverse=True)
print("Top 5 most similar pairs:")
for sim, p1, p2 in sim_flat[:5]:
    print(f"  {p1} <-> {p2}: {sim:.3f}")
print("Top 3 most different pairs:")
for sim, p1, p2 in sim_flat[-3:]:
    print(f"  {p1} <-> {p2}: {sim:.3f}")

print("\n=== KNOWLEDGE GAP INSIGHTS ===")
print("Biggest gaps (project, type, gap):")
gap_list = []
for i in range(len(projects)):
    for j in range(len(knowledge_types)):
        if gaps[i, j] >= 5:
            gap_list.append((gaps[i, j], projects[i], knowledge_types[j]))
gap_list.sort(reverse=True)
for g, p, t in gap_list:
    print(f"  {p} / {t}: -{int(g)}")

print("\n=== AGENTIC ROI RANKING ===")
for i in roi_order:
    print(
        f"  {projects[i]}: ROI={roi[i]:.1f} (WHY={data[i, 3]}, UNSAID={data[i, 4]}, size~{size_estimate[i]})"
    )
