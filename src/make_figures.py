#!/usr/bin/env python3
"""Generate publication-grade minimalist figures for ProofDistill README & ANALYSIS.

Reads exact full-corpus metrics from `data/deep_causal_anatomy.json` and writes
vector SVG + 300 DPI PNG figures to `figures/`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "deep_causal_anatomy.json"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Clean academic palette (derived from scientific-figure-making house style)
BLUE_DARK = "#0F4D92"
BLUE_MID = "#3775BA"
BLUE_LIGHT = "#EBF2FA"
RED_DARK = "#B64342"
RED_MID = "#D16D6A"
RED_LIGHT = "#FBECEB"
GREEN_DARK = "#246B4F"
GREEN_LIGHT = "#EAF5F0"
SLATE_DARK = "#22272E"
SLATE_MID = "#57606A"
SLATE_LIGHT = "#D0D7DE"
SLATE_BG = "#F6F8FA"

plt.rcParams.update({
    "font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"],
    "axes.edgecolor": SLATE_MID,
    "axes.linewidth": 1.1,
    "svg.fonttype": "none",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def make_fig1_anatomy() -> None:
    d = json.loads(DATA_PATH.read_text())
    ml = d["mathlib"]
    rh = d["rh_in_cone"]

    ml_lines = ml["stats"]["total_lines"]
    rh_lines = rh["stats"]["total_lines"]
    ml_thms = ml["decl_kinds"]["theorem"] + ml["decl_kinds"]["lemma"]
    rh_thms = rh["decl_kinds"]["theorem"] + rh["decl_kinds"]["lemma"]

    # Panel A data: exact mutually-exclusive live kernel cone line breakdown (15,218,364 lines)
    lb = rh["lines_breakdown"]
    stmt_l = lb["stmt_or_glue_files"]                  # 691,632 (4.54%)
    dump_l = lb["non_stmt_with_dump_strict"]           # 114,282 (0.75%)
    clean_l = lb["non_stmt_clean_strict"]              # 14,412,450 (94.70%)

    # Panel B data: exact ratios (AI RH vs Mathlib = 1x)
    ml_class_per_m = ml["decl_kinds"]["class"] / (ml_lines / 1e6)
    rh_class_per_m = rh["decl_kinds"]["class"] / (rh_lines / 1e6)

    ml_ext_per_m = ml["stats"]["ext_attrs"] / (ml_lines / 1e6)
    rh_ext_per_m = rh["stats"]["ext_attrs"] / (rh_lines / 1e6)

    ml_simp_pct = 100.0 * ml["stats"]["simp_attrs"] / ml_thms
    rh_simp_pct = 100.0 * rh["stats"]["simp_attrs"] / rh_thms

    ml_inst_per_s = ml["decl_kinds"]["instance"] / ml["decl_kinds"]["structure"]
    rh_inst_per_s = rh["decl_kinds"]["instance"] / rh["decl_kinds"]["structure"]

    ml_long50_pct = 100.0 * (ml["proof_len_buckets"]["51-150"] + ml["proof_len_buckets"]["151-500"] + ml["proof_len_buckets"]["500+"]) / ml_thms
    rh_long50_pct = 100.0 * (rh["proof_len_buckets"]["51-150"] + rh["proof_len_buckets"]["151-500"] + rh["proof_len_buckets"]["500+"]) / rh_thms

    ml_defprop_pct = 100.0 * ml["stats"]["def_prop_lines"] / ml["stats"]["def_lines"]
    rh_defprop_pct = 100.0 * rh["stats"]["def_prop_lines"] / rh["stats"]["def_lines"]

    ml_have_1k = ml["stats"]["have_lines"] / (ml_lines / 1e3)
    rh_have_1k = rh["stats"]["have_lines"] / (rh_lines / 1e3)

    ml_indeg1 = ml["indeg_non_stmt"]["pct_eq_1"]
    rh_indeg1 = rh["indeg_non_stmt"]["pct_eq_1"]

    rows = [
        ("class density\n(per 1M lines)", rh_class_per_m / ml_class_per_m,
         "2.2 vs 853", "deficit"),
        ("@[ext] density\n(per 1M lines)", rh_ext_per_m / ml_ext_per_m,
         "6.8 vs 590", "deficit"),
        ("@[simp] share\n(% of theorems)", rh_simp_pct / ml_simp_pct,
         "0.83% vs 27.8%", "deficit"),
        ("instance per\nstructure", rh_inst_per_s / ml_inst_per_s,
         "0.57 vs 6.06", "deficit"),
        ("Theorems >50 lines\n(% of theorems)", rh_long50_pct / ml_long50_pct,
         "6.36% vs 0.55%", "excess"),
        ("def : Prop ratio\n(% of defs)", rh_defprop_pct / ml_defprop_pct,
         "37.1% vs 3.3%", "excess"),
        ("Manual have rate\n(per 1k lines)", rh_have_1k / ml_have_1k,
         "124.3 vs 17.1", "excess"),
        ("Single-caller files\n(non-wrapper in-deg=1)", rh_indeg1 / ml_indeg1,
         "56.1% vs 29.8%", "excess"),
    ]

    fig = plt.figure(figsize=(11.8, 7.8), dpi=300)

    # Full-width top Panel A for clean editorial alignment
    ax_a = fig.add_axes([0.05, 0.70, 0.91, 0.17])
    ax_a.set_xlim(0, 100)
    ax_a.set_ylim(-0.62, 0.85)
    ax_a.axis("off")

    ax_a.text(
        0, 0.68,
        "A.  Live Kernel Cone Breakdown (15.22M lines across 147,489 files)",
        fontsize=12.2, fontweight="bold", color=SLATE_DARK, va="bottom", ha="left",
    )

    p_stmt = 100.0 * stmt_l / rh_lines
    p_dump = 100.0 * dump_l / rh_lines
    p_clean = 100.0 * clean_l / rh_lines

    y0, h = 0.04, 0.44
    segments = [
        (0.0, p_stmt, "#7C8694"),
        (p_stmt, p_dump, "#B3BCC6"),
        (p_stmt + p_dump, p_clean, BLUE_DARK),
    ]
    for left, width, color in segments:
        ax_a.barh(y0 + h / 2, width, left=left, height=h, color=color, edgecolor="white", linewidth=1.3)

    ax_a.text(
        (p_stmt + p_dump) + p_clean / 2, y0 + h / 2,
        f"Clean, non-wrapper, non-dump live Lean code:  14.41M lines ({p_clean:.1f}%)",
        color="white", fontsize=11.0, fontweight="bold", ha="center", va="center",
    )

    mech_end = p_stmt + p_dump
    ax_a.plot([0.15, 0.15, mech_end - 0.1, mech_end - 0.1], [-0.04, -0.14, -0.14, -0.04],
              color=SLATE_MID, linewidth=1.15)
    ax_a.text(
        0.15, -0.24,
        f"Surface wrappers & dumps ({mech_end:.1f}%):  *Statement/glue 4.54% (692k) · strict explicit dumps 0.75% (114k, 717 files)   |   maxHeartbeats lines across cone: ~76k (~0.5%)",
        fontsize=8.9, color=SLATE_MID, ha="left", va="top",
    )

    # ---- Panel B: Diverging Log-Fold-Change vs Mathlib Baseline ----
    ax_b = fig.add_axes([0.21, 0.09, 0.75, 0.51])
    y_pos = np.arange(len(rows))[::-1]
    log_vals = [math.log10(r[1]) for r in rows]
    colors = [BLUE_MID if r[3] == "deficit" else RED_DARK for r in rows]

    xmin, xmax = -4.55, 2.95
    ax_b.axvspan(xmin, 0, color=BLUE_LIGHT, alpha=0.38, zorder=0)
    ax_b.axvspan(0, xmax, color=RED_LIGHT, alpha=0.38, zorder=0)

    ax_b.axhline(3.5, color=SLATE_LIGHT, linestyle="--", linewidth=1.0, zorder=1)
    ax_b.axvline(0, color=SLATE_DARK, linestyle="-", linewidth=1.4, zorder=2)

    for xv in [-3, -2, -1, 1, 2]:
        ax_b.axvline(xv, color=SLATE_LIGHT, linestyle=":", linewidth=0.8, zorder=1)

    ax_b.barh(y_pos, log_vals, height=0.58, color=colors, edgecolor="none", zorder=3)

    for y, (lbl, ratio, raw, grp), lv in zip(y_pos, rows, log_vals):
        if grp == "deficit":
            fold = 1.0 / ratio
            fold_str = f"{fold:.0f}× lower" if fold >= 100 else f"{fold:.1f}× lower"
            ax_b.text(
                lv - 0.08, y, f"{fold_str}  ({raw})",
                ha="right", va="center", fontsize=9.2, fontweight="bold", color=BLUE_DARK, zorder=4,
            )
        else:
            fold_str = f"{ratio:.1f}× higher"
            ax_b.text(
                lv + 0.08, y, f"{fold_str}  ({raw})",
                ha="left", va="center", fontsize=9.2, fontweight="bold", color=RED_DARK, zorder=4,
            )

    ax_b.set_yticks(y_pos)
    ax_b.set_yticklabels([r[0] for r in rows], fontsize=9.6, color=SLATE_DARK)
    ax_b.set_xlim(xmin, xmax)
    ax_b.set_ylim(-0.65, len(rows) - 0.08)
    ax_b.set_xticks([-3, -2, -1, 0, 1, 2])
    ax_b.set_xticklabels(["1000×\nlower", "100×\nlower", "10×\nlower", "1×\n(Mathlib)", "10×\nhigher", "100×\nhigher"],
                         fontsize=9.2, color=SLATE_MID)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.spines["left"].set_visible(False)
    ax_b.tick_params(axis="y", length=0, pad=9)

    ax_b.text(-2.25, len(rows) - 0.24, "← Missing Theory & Automation Layer",
              fontsize=9.7, fontweight="bold", color=BLUE_DARK, ha="center", va="bottom")
    ax_b.text(1.48, len(rows) - 0.24, "Contract-Frozen & Manual-Chaining Tax →",
              fontsize=9.7, fontweight="bold", color=RED_DARK, ha="center", va="bottom")

    # Align Panel B title cleanly with Panel A left edge
    fig.text(
        0.05, 0.635,
        "B.  AI RH Live Cone (147,489 files) Relative to Human Mathlib (8,712 files)  [log10 fold-change]",
        fontsize=12.2, fontweight="bold", color=SLATE_DARK, ha="left", va="bottom",
    )

    fig.text(
        0.05, 0.945,
        "Why Mechanical Cleanups Leave >94% of the 15.22M-Line AI RH Proof Behind",
        fontsize=15.0, fontweight="bold", color=SLATE_DARK, ha="left", va="top",
    )
    fig.text(
        0.05, 0.905,
        "Exact full-corpus structural scan: Alpöge RH kernel cone (147,489 files, 15.22M lines) vs. Mathlib v4.36 (8,712 files, 2.37M lines)",
        fontsize=9.4, color=SLATE_MID, ha="left", va="top",
    )

    for ext in ("png", "svg"):
        out = FIG_DIR / f"fig1_mathlib_vs_rh.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)
    print("Saved figures/fig1_mathlib_vs_rh.{png,svg}")


def make_fig1_three_factor() -> None:
    """Publication-grade 3x3 small-multiples figure: Orthogonal 3-Factor Decomposition
    across Mathlib, Pure Human Research (3 repos), FLT (Human-Curated + AI), PNT+ Core,
    PNT+/IEANTN (2026 AI PRs), and Alpöge RH Live Cone.
    """
    tw = json.loads((ROOT / "data" / "three_way_comparison.json").read_text())
    by_name = {r["name"]: r for r in tw["summary_table"]}

    corpora = [
        ("Mathlib v4.36 (StdLib)", "Mathlib v4.36\n(StdLib)", "#7D8590"),
        ("Pure Human Research (3 repos)", "Pure Human (3)\n(0 AI mentions)", "#246B4F"),
        ("FLT", "FLT\n(Human + 26 AI)", "#0F4D92"),
        ("PNT+ Core (excl. IEANTN)", "PNT+ Core\n(Analytic NT)", "#5B8EC9"),
        ("PNT+/IEANTN (2026 AI PRs)", "PNT+/IEANTN\n(2026 AI PRs)", "#D0831A"),
        ("Alpöge RH Live Cone (AI)", "Alpöge RH\n(Parallel AI)", "#B64342"),
    ]
    rows_data = [by_name[k] for k, _, _ in corpora]
    y_labels = [lbl for _, lbl, _ in corpora]
    colors = [c for _, _, c in corpora]
    y_pos = np.arange(len(corpora))[::-1]

    row_specs = [
        (
            "Factor 1 · StdLib vs. Frontier Research  (Falsified as AI-Only — Human Research Matches RH)",
            "#F6F8FA",
            "#D0D7DE",
            SLATE_DARK,
            [
                ("Theorems >50 lines (%)", "long50_pct_of_thms", lambda v: f"{v:.1f}%", 12.2),
                ("Single-caller files (in-deg = 1, %)", "indeg_eq_1_pct", lambda v: f"{v:.1f}%", 86.0),
                ("Manual have rate (per 1k lines)", "have_per_1k_lines", lambda v: f"{v:.0f}", 162.0),
            ],
        ),
        (
            "Factor 2 · Autonomous LLM Abstraction Collapse  (Prevented by Human Curation in FLT)",
            "#F3F8FD",
            "#BDD3EA",
            BLUE_DARK,
            [
                ("class density (per 1M lines)", "class_per_1m_lines", lambda v: f"{v:.1f}" if v < 50 else f"{v:.0f}", 1130.0),
                ("@[simp] share (% of theorems)", "simp_pct_of_thms", lambda v: f"{v:.2f}%" if v < 1 else f"{v:.1f}%", 36.5),
                ("instance / structure ratio", "inst_per_struct", lambda v: f"{v:.2f}", 7.9),
            ],
        ),
        (
            "Factor 3 · Parallel Multi-Agent Orchestrator Signatures  (Unique to Alpöge RH)",
            "#FDF6F6",
            "#E6C9C8",
            RED_DARK,
            [
                ("Monolithic import Mathlib (% files)", "import_mathlib_root_pct", lambda v: f"{v:.1f}%", 102.0),
                ("Frozen def : Prop (% of defs)", "def_prop_pct", lambda v: f"{v:.1f}%", 49.5),
                ("Avg file size (lines / file; ↓ = fragmented)", "avg_lines_per_file", lambda v: f"{v:.0f} L", 1240.0),
            ],
        ),
    ]

    fig = plt.figure(figsize=(13.4, 11.6), dpi=300)

    # Background axes at zorder=0 so rounded row bands ALWAYS render behind all data axes
    bg_ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], zorder=0)
    bg_ax.set_xlim(0.0, 1.0)
    bg_ax.set_ylim(0.0, 1.0)
    bg_ax.axis("off")

    # Global title & subtitle
    bg_ax.text(
        0.025, 0.978,
        "Separating StdLib Confounds, LLM Abstraction Collapse, and Parallel-Agent Signatures",
        fontsize=15.4, fontweight="bold", color=SLATE_DARK, ha="left", va="top",
    )
    bg_ax.text(
        0.025, 0.949,
        "Identical full-corpus analyzer run across Mathlib v4.36 (8,712 files), 3 pure-human research repos (Carleson, SphereEversion, PFR; 259 files, 0 AI mentions), "
        "FLT (260 files; human-curated w/ 26 AI-credit files),\nPrimeNumberTheoremAnd split (Core 107 files vs. IEANTN 126 files), and Alpöge RH live kernel cone (147,489 files; post-#150 v4.36 main: 77.6% import Mathlib).",
        fontsize=8.9, color=SLATE_MID, ha="left", va="top", linespacing=1.38,
    )

    row_bottoms = [0.642, 0.340, 0.038]
    row_height = 0.194
    col_lefts = [0.165, 0.445, 0.725]
    col_width = 0.242

    for r_idx, (row_title, bg_fc, bg_ec, title_col, panels) in enumerate(row_specs):
        rb = row_bottoms[r_idx]
        band = FancyBboxPatch(
            (0.022, rb - 0.024), 0.958, row_height + 0.080,
            boxstyle="round,pad=0.004,rounding_size=0.012",
            facecolor=bg_fc, edgecolor=bg_ec, linewidth=1.05, zorder=1,
        )
        bg_ax.add_patch(band)
        bg_ax.text(
            0.036, rb + row_height + 0.036,
            row_title,
            fontsize=10.6, fontweight="bold", color=title_col, ha="left", va="center", zorder=2,
        )

        for c_idx, (ptitle, key, fmt, xmax) in enumerate(panels):
            ax = fig.add_axes([col_lefts[c_idx], rb, col_width, row_height], zorder=5)
            ax.set_facecolor("white")
            vals = [row[key] if row[key] is not None else 0.0 for row in rows_data]

            ax.barh(y_pos, vals, height=0.62, color=colors, edgecolor="none", zorder=3)
            ax.set_xlim(0, xmax)
            ax.set_ylim(-0.62, len(corpora) - 0.38)
            ax.grid(axis="x", linestyle=":", linewidth=0.75, color="#DCE2E8", zorder=1)
            ax.set_axisbelow(True)

            for y, v, col in zip(y_pos, vals, colors):
                is_hi = (
                    (r_idx == 1 and col in ("#D0831A", "#B64342", "#0F4D92"))
                    or (r_idx == 2 and col == "#B64342")
                )
                txt_col = col if is_hi else SLATE_DARK
                fw = "bold" if is_hi else "normal"
                ax.text(
                    v + xmax * 0.022, y, fmt(v),
                    ha="left", va="center", fontsize=8.3, fontweight=fw, color=txt_col, zorder=4,
                )

            ax.set_title(ptitle, fontsize=9.1, fontweight="bold", color=SLATE_DARK, loc="left", pad=5)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color(SLATE_LIGHT)
            ax.spines["bottom"].set_color(SLATE_LIGHT)
            ax.tick_params(axis="x", labelsize=7.7, colors=SLATE_MID, length=2.5)
            ax.xaxis.set_major_locator(plt.MaxNLocator(4))

            if c_idx == 0:
                ax.set_yticks(y_pos)
                ax.set_yticklabels(y_labels, fontsize=8.0, color=SLATE_DARK, linespacing=1.08)
                ax.tick_params(axis="y", length=0, pad=6)
            else:
                ax.set_yticks(y_pos)
                ax.set_yticklabels([])
                ax.tick_params(axis="y", length=0)

    for ext in ("png", "svg"):
        out = FIG_DIR / f"fig1_three_factor_anatomy.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("Saved figures/fig1_three_factor_anatomy.{png,svg}")


def make_fig2_architecture() -> None:
    """Crisp minimalist vector schematic contrasting Wake-Only vs Theory-Lifting / Wake-Sleep."""
    fig, ax = plt.subplots(figsize=(12.0, 6.2), dpi=300)
    ax.set_xlim(0, 12.0)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    def draw_box(x, y, w, h, title, body, fc, ec, tc=SLATE_DARK, title_size=10.0, body_size=8.5, lw=1.4):
        box = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3,
        )
        ax.add_patch(box)
        ax.text(x + w / 2, y + h * 0.68, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold", color=tc, zorder=4)
        if body:
            ax.text(x + w / 2, y + h * 0.30, body, ha="center", va="center",
                    fontsize=body_size, color=SLATE_MID, zorder=4, linespacing=1.25)

    def draw_arrow(x1, y1, x2, y2, color=SLATE_MID, rad=0.0, ls="-", lw=1.5):
        arr = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>,head_length=6.5,head_width=3.8",
            connectionstyle=f"arc3,rad={rad}",
            color=color, linewidth=lw, linestyle=ls, zorder=5,
        )
        ax.add_patch(arr)

    # Title
    ax.text(0.25, 5.88, "From 'Wake-Only' Parallel Proving to Subtree Theory-Lifting & Wake–Sleep Consolidation",
            fontsize=13.8, fontweight="bold", color=SLATE_DARK, ha="left", va="center")
    ax.text(0.25, 5.54, "Why single-file export-locked edits hit an abstraction ceiling — and why unlocking dominated subtree interiors breaks it",
            fontsize=9.3, color=SLATE_MID, ha="left", va="center")

    # ---- TOP LANE: Current Wake-Only Architecture ----
    top_bg = FancyBboxPatch((0.2, 3.18), 11.6, 2.08, boxstyle="round,pad=0.04,rounding_size=0.14",
                            facecolor="#FDF8F8", edgecolor="#E6C9C8", linewidth=1.1, zorder=1)
    ax.add_patch(top_bg)
    ax.text(0.42, 5.02, "1.  Observed Paradigm: 'Wake-Only' Contract-Frozen Parallel Synthesis  (Verified Factor 2 & 3 Signatures)",
            fontsize=10.5, fontweight="bold", color=RED_DARK, ha="left", va="center", zorder=2)

    y_top, bh = 3.72, 1.02
    draw_box(0.42, y_top, 2.35, bh, "Freeze Interfaces Up Front",
             "65,028 def : Prop handoffs\n(37.1% vs 7.4% pure human)", "white", RED_MID, RED_DARK)
    draw_box(3.22, y_top, 2.45, bh, "Isolated Parallel Workers",
             "6,836 bare structs · 2.2 class/M\n0.57 inst/struct · 0.83% @[simp]", "white", RED_MID, RED_DARK)
    draw_box(6.12, y_top, 2.42, bh, "Import & Micro-File Tax",
             "76.0% monolithic import Mathlib\n103 L/file (3.2× smaller vs human)", "white", RED_MID, RED_DARK)
    draw_box(8.98, y_top, 2.60, bh, "15.22M-Line Brittle Tree",
             "Automation starved (1.89M have)\n95× fewer classes/M vs human", RED_LIGHT, RED_DARK, RED_DARK, lw=1.7)

    draw_arrow(2.81, y_top + bh / 2, 3.18, y_top + bh / 2, RED_DARK)
    draw_arrow(5.71, y_top + bh / 2, 6.08, y_top + bh / 2, RED_DARK)
    draw_arrow(8.58, y_top + bh / 2, 8.94, y_top + bh / 2, RED_DARK)

    # Bottom caption bar inside top lane
    ax.text(0.42, 3.38,
            "Why post-hoc single-file cleanups hit a wall: mechanical PRs trim ~5.3% exhaust; Phase A export-locked single-file edits (+9L, -0.45% hb) cannot melt cross-file boundaries.",
            fontsize=8.4, style="italic", color=SLATE_MID, ha="left", va="center", zorder=4)

    # ---- BOTTOM LANE: Proposed Theory-Lifting / Wake-Sleep ----
    bot_bg = FancyBboxPatch((0.2, 0.22), 11.6, 2.66, boxstyle="round,pad=0.04,rounding_size=0.14",
                            facecolor="#F5F9FC", edgecolor="#BDD3EA", linewidth=1.1, zorder=1)
    ax.add_patch(bot_bg)
    ax.text(0.42, 2.64, "2.  Next Solution: Subtree-Boundary Theory-Lifting  (Phase B)  &  Human/Wake–Sleep Curation  (FLT Pattern)",
            fontsize=10.5, fontweight="bold", color=BLUE_DARK, ha="left", va="center", zorder=2)

    y_bot, bh2 = 1.24, 1.10
    draw_box(0.42, y_bot, 2.35, bh2, "Dominated Subtree Unit",
             "Lock ONLY root exit exports\nvia Kernel.isDefEq + 3 axioms", "white", BLUE_MID, BLUE_DARK)
    draw_box(3.25, y_bot, 2.75, bh2, "Retroactive API & Lifting",
             "• Synthesize instance / @[simp] / @[ext]\n• Melt internal def : Prop & micro-files", "white", BLUE_MID, BLUE_DARK)
    draw_box(6.48, y_bot, 2.35, bh2, "Cross-Branch Reuse",
             "Anti-unify sibling proofs\nTrim monolithic Mathlib imports", "white", BLUE_MID, BLUE_DARK)
    draw_box(9.30, y_bot, 2.28, bh2, "Mathlib-Grade Subtree",
             "Fewer files, tokens & heartbeats\nUnedited callers compile clean", GREEN_LIGHT, GREEN_DARK, GREEN_DARK, lw=1.7)

    draw_arrow(2.81, y_bot + bh2 / 2, 3.21, y_bot + bh2 / 2, BLUE_DARK)
    draw_arrow(6.04, y_bot + bh2 / 2, 6.44, y_bot + bh2 / 2, BLUE_DARK)
    draw_arrow(8.87, y_bot + bh2 / 2, 9.26, y_bot + bh2 / 2, GREEN_DARK)

    # Sleep consolidation feedback loop at bottom of lane 2
    ax.plot([10.44, 10.44, 1.60, 1.60], [1.20, 0.56, 0.56, 1.18],
            color=GREEN_DARK, linestyle="--", linewidth=1.35, zorder=4)
    draw_arrow(1.60, 0.92, 1.60, 1.22, GREEN_DARK, ls="--", lw=1.35)
    ax.text(
        6.02, 0.56,
        "  Sleep Consolidation Gate (Generation-Time): enforce FLT/Mathlib invariants (class/M, inst/struct, @[simp]%, targeted imports) before spawning deeper workers  ",
        fontsize=8.3, fontweight="bold", color=GREEN_DARK, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#F5F9FC", edgecolor="none"), zorder=5,
    )

    fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.02)
    for ext in ("png", "svg"):
        out = FIG_DIR / f"fig2_wake_sleep_architecture.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("Saved figures/fig2_wake_sleep_architecture.{png,svg}")


if __name__ == "__main__":
    make_fig1_anatomy()
    make_fig1_three_factor()
    make_fig2_architecture()
