#!/usr/bin/env python3
"""Heatmap comparison: Calorie Skill (Sim2) vs Flight Skill (Sim3)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ===== Data based on actual extraction results =====

# Knowledge types
ktypes = ["WHAT", "HOW", "IF/RULES", "WHY", "UNSAID", "STRUCTURE"]

# Sim2: Calorie projects (GitHub)
cal_github = {
    "ai-calorie-\ncounter": [7, 8, 8, 9, 7, 5],  # Small but dense, strong WHY (JSON contract, BMR)
    "FoodYou": [9, 8, 9, 7, 6, 9],  # 43 fields, complex structure, good rules
    "OpenNutri-\nTracker": [8, 8, 8, 8, 7, 8],  # Balanced, strong formulas, good UNSAID
}
# Sim2: Calorie community (aggregated)
cal_community = {
    "Community\n(4 skills)": [7, 5, 6, 2, 2, 4],  # WHAT ok, patterns ok, zero WHY/UNSAID
}

# Sim3: Flight projects (GitHub)
flt_github = {
    "fast-\nflights": [7, 9, 7, 8, 8, 6],  # Deep protocol reverse engineering, strong UNSAID
    "Travel\nPlanner": [5, 7, 6, 6, 7, 4],  # Algorithm-focused, UNSAID from bugs
    "gpt-search-\nflights": [6, 8, 7, 9, 8, 5],  # Strong WHY (function calling pattern), UNSAID
}
# Sim3: Flight community (aggregated)
flt_community = {
    "Community\n(8 skills)": [8, 5, 6, 2, 1, 5],  # Good WHAT (features), zero WHY/UNSAID
}

fig = plt.figure(figsize=(18, 16))

# ===== Plot 1: Calorie full heatmap =====
ax1 = fig.add_subplot(2, 2, 1)
cal_all = {**cal_github, **cal_community}
cal_names = list(cal_all.keys())
cal_data = np.array(list(cal_all.values()))

im1 = ax1.imshow(cal_data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)
ax1.set_xticks(range(len(ktypes)))
ax1.set_xticklabels(ktypes, fontsize=9, fontweight="bold")
ax1.set_yticks(range(len(cal_names)))
ax1.set_yticklabels(cal_names, fontsize=9)
for i in range(len(cal_names)):
    for j in range(len(ktypes)):
        v = cal_data[i, j]
        c = "white" if v < 4 or v > 8 else "black"
        ax1.text(j, i, str(v), ha="center", va="center", fontsize=11, fontweight="bold", color=c)
    # Color bar: GitHub=red, Community=blue
    color = "#e74c3c" if i < len(cal_github) else "#3498db"
    ax1.add_patch(
        plt.Rectangle((-0.7, i - 0.4), 0.25, 0.8, facecolor=color, edgecolor="none", clip_on=False)
    )
ax1.set_title("Sim2: Calorie Tracker", fontsize=12, fontweight="bold", pad=10)

# ===== Plot 2: Flight full heatmap =====
ax2 = fig.add_subplot(2, 2, 2)
flt_all = {**flt_github, **flt_community}
flt_names = list(flt_all.keys())
flt_data = np.array(list(flt_all.values()))

im2 = ax2.imshow(flt_data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)
ax2.set_xticks(range(len(ktypes)))
ax2.set_xticklabels(ktypes, fontsize=9, fontweight="bold")
ax2.set_yticks(range(len(flt_names)))
ax2.set_yticklabels(flt_names, fontsize=9)
for i in range(len(flt_names)):
    for j in range(len(ktypes)):
        v = flt_data[i, j]
        c = "white" if v < 4 or v > 8 else "black"
        ax2.text(j, i, str(v), ha="center", va="center", fontsize=11, fontweight="bold", color=c)
    color = "#e74c3c" if i < len(flt_github) else "#3498db"
    ax2.add_patch(
        plt.Rectangle((-0.7, i - 0.4), 0.25, 0.8, facecolor=color, edgecolor="none", clip_on=False)
    )
ax2.set_title("Sim3: Flight Search", fontsize=12, fontweight="bold", pad=10)

# Legend for both
legend_elements = [
    plt.Rectangle((0, 0), 1, 1, facecolor="#e74c3c", label="GitHub Project"),
    plt.Rectangle((0, 0), 1, 1, facecolor="#3498db", label="Community Skill"),
]
ax2.legend(handles=legend_elements, loc="lower right", fontsize=8)

# ===== Plot 3: GitHub vs Community comparison =====
ax3 = fig.add_subplot(2, 2, 3)

# Average GitHub vs Community for each sim
cal_gh_avg = np.array(list(cal_github.values())).mean(axis=0)
cal_cm_avg = np.array(list(cal_community.values())).mean(axis=0)
flt_gh_avg = np.array(list(flt_github.values())).mean(axis=0)
flt_cm_avg = np.array(list(flt_community.values())).mean(axis=0)

x = np.arange(len(ktypes))
w = 0.2
ax3.bar(x - 1.5 * w, cal_gh_avg, w, label="Calorie GitHub", color="#e74c3c", alpha=0.8)
ax3.bar(x - 0.5 * w, cal_cm_avg, w, label="Calorie Community", color="#e74c3c", alpha=0.4)
ax3.bar(x + 0.5 * w, flt_gh_avg, w, label="Flight GitHub", color="#2980b9", alpha=0.8)
ax3.bar(x + 1.5 * w, flt_cm_avg, w, label="Flight Community", color="#2980b9", alpha=0.4)

ax3.set_xticks(x)
ax3.set_xticklabels(ktypes, fontsize=9, fontweight="bold")
ax3.set_ylabel("Avg Density", fontsize=10)
ax3.set_ylim(0, 10)
ax3.set_title("GitHub vs Community: Knowledge Gap", fontsize=12, fontweight="bold", pad=10)
ax3.legend(fontsize=7, loc="upper right")
ax3.grid(axis="y", alpha=0.3)

# Annotate the gap
for i, kt in enumerate(ktypes):
    if kt in ["WHY", "UNSAID"]:
        gap_cal = cal_gh_avg[i] - cal_cm_avg[i]
        gap_flt = flt_gh_avg[i] - flt_cm_avg[i]
        ax3.annotate(
            f"Gap\n{gap_cal:.0f}/{gap_flt:.0f}",
            xy=(i, max(cal_gh_avg[i], flt_gh_avg[i]) + 0.3),
            fontsize=7,
            ha="center",
            color="red",
            fontweight="bold",
        )

# ===== Plot 4: Cross-domain knowledge profile =====
ax4 = fig.add_subplot(2, 2, 4)

# Combined (GitHub + Community weighted average) per sim
cal_combined = cal_gh_avg * 0.7 + cal_cm_avg * 0.3  # GitHub weighted more
flt_combined = flt_gh_avg * 0.7 + flt_cm_avg * 0.3

# Radar-like horizontal bar comparison
y = np.arange(len(ktypes))
ax4.barh(y + 0.15, cal_combined, 0.3, label="Calorie Skill", color="#27ae60", alpha=0.8)
ax4.barh(y - 0.15, flt_combined, 0.3, label="Flight Skill", color="#8e44ad", alpha=0.8)

ax4.set_yticks(y)
ax4.set_yticklabels(ktypes, fontsize=10, fontweight="bold")
ax4.set_xlim(0, 10)
ax4.set_xlabel("Combined Density (GitHub 70% + Community 30%)", fontsize=9)
ax4.set_title("Cross-Domain Knowledge Profile", fontsize=12, fontweight="bold", pad=10)
ax4.legend(fontsize=9)
ax4.grid(axis="x", alpha=0.3)

# Add value labels
for i in range(len(ktypes)):
    ax4.text(
        cal_combined[i] + 0.1,
        i + 0.15,
        f"{cal_combined[i]:.1f}",
        va="center",
        fontsize=8,
        color="#27ae60",
    )
    ax4.text(
        flt_combined[i] + 0.1,
        i - 0.15,
        f"{flt_combined[i]:.1f}",
        va="center",
        fontsize=8,
        color="#8e44ad",
    )

fig.suptitle(
    "Doramagic: Calorie vs Flight Skill — Knowledge Extraction Heatmap",
    fontsize=14,
    fontweight="bold",
    y=0.98,
)
plt.tight_layout(rect=[0, 0, 1, 0.96])

output = "/Users/tang/Documents/vibecoding/Doramagic/research/heatmap-sim2-vs-sim3.png"
plt.savefig(output, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Saved: {output}")

# Print insights
print("\n=== KEY INSIGHTS ===")
print("\nGitHub vs Community WHY gap:")
print(
    f"  Calorie: GitHub={cal_gh_avg[3]:.1f} vs Community={cal_cm_avg[3]:.1f} (gap={cal_gh_avg[3] - cal_cm_avg[3]:.1f})"
)
print(
    f"  Flight:  GitHub={flt_gh_avg[3]:.1f} vs Community={flt_cm_avg[3]:.1f} (gap={flt_gh_avg[3] - flt_cm_avg[3]:.1f})"
)

print("\nGitHub vs Community UNSAID gap:")
print(
    f"  Calorie: GitHub={cal_gh_avg[4]:.1f} vs Community={cal_cm_avg[4]:.1f} (gap={cal_gh_avg[4] - cal_cm_avg[4]:.1f})"
)
print(
    f"  Flight:  GitHub={flt_gh_avg[4]:.1f} vs Community={flt_cm_avg[4]:.1f} (gap={flt_gh_avg[4] - flt_cm_avg[4]:.1f})"
)

print("\nCross-domain profile comparison:")
for i, kt in enumerate(ktypes):
    diff = cal_combined[i] - flt_combined[i]
    winner = "Calorie" if diff > 0 else "Flight"
    print(
        f"  {kt}: Calorie={cal_combined[i]:.1f} vs Flight={flt_combined[i]:.1f} ({winner} +{abs(diff):.1f})"
    )
