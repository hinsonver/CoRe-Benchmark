"""Compact recovery panels from existing saved counts; no new inference or runs.

The identifier and year numerators come from the saved Movies column table.
The previously reported middle-year rule is 167/190, whose rounded accuracy
must agree with fig2_year_range.csv before this figure can be regenerated.
"""
import csv
from dataclasses import dataclass
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .data import ROOT

PROJECT = ROOT
NAME = "fig1_recovery_evidence"
COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")


@dataclass
class RecoveryFigure:
    """Keep the real artists available for print-geometry inspection."""
    figure: object
    axes: tuple
    rows: list[dict]
    bars: dict
    rule_line: object
    paths: dict


def recovery_rows() -> list[dict]:
    """Read saved repair counts and check the previously saved year accuracies."""
    source = "results/tables/moviescols.tex"
    table = (PROJECT / source).read_text()
    counts = {}
    for column in ("identifier", "year"):
        line = next(line for line in table.splitlines() if line.strip().startswith(column + " &"))
        values = [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*/\s*(\d+)", line)]
        if len(values) != 4:
            raise ValueError(f"Expected four saved condition counts for {column}")
        counts[column] = dict(zip("OFWS", values))
    rule_correct, rule_total = 167, 190
    with (PROJECT / "results/figures/fig2_year_range.csv").open(newline="") as handle:
        year_source = dict(zip("OWS", csv.DictReader(handle)))
    rows = []
    for panel, conditions in (("identifier", "OFWS"), ("year", "OWS")):
        for condition in conditions:
            repaired, errors = counts[panel][condition]
            if panel == "year":
                saved = year_source[condition]
                if (round(repaired / errors, 3) != float(saved["accuracy"]) or
                        round(rule_correct / rule_total, 3) != float(saved["middle_rule_accuracy"])):
                    raise ValueError(f"Saved year evidence disagrees for {condition}")
            rows.append({
                "dataset": "Movies", "model": "DeepSeek-V4-Pro", "panel": panel,
                "condition": condition, "comparison": "nonpaired" if condition == "F" else "paired",
                "repaired": repaired, "errors": errors, "repair_fraction": repaired / errors,
                "middle_rule_correct": rule_correct if panel == "year" else "",
                "middle_rule_total": rule_total if panel == "year" else "",
                "middle_rule_fraction": rule_correct / rule_total if panel == "year" else "",
                "repair_source": source,
                "rule_source": "results/figures/fig2_year_range.csv" if panel == "year" else "",
            })
    return rows


def render_recovery_evidence(output_dir: Path, colors=COLORS) -> RecoveryFigure:
    """Export at exact column size, returning artists for independent inspection."""
    rows = recovery_rows()
    color = dict(zip("OFWS", colors))
    style = {"font.family": "DejaVu Sans", "font.size": 6.2, "axes.titlesize": 6.5,
             "axes.titleweight": "bold", "axes.labelsize": 6.2, "xtick.labelsize": 6.5,
             "ytick.labelsize": 6.0, "axes.edgecolor": "#aaa9a4", "axes.linewidth": 0.5,
             "axes.labelcolor": "#333333", "xtick.color": "#333333", "ytick.color": "#52514e",
             "axes.grid": False, "axes.spines.top": False, "axes.spines.right": False,
             "figure.facecolor": "white", "axes.facecolor": "white", "pdf.fonttype": 42,
             "svg.fonttype": "none"}
    with plt.rc_context(style):
        figure, axes = plt.subplots(1, 2, figsize=(3.33, 1.65), dpi=150, sharey=True,
                                    gridspec_kw={"width_ratios": [1.18, 1]})
        figure.subplots_adjust(left=0.14, right=0.985, bottom=0.27, top=0.73, wspace=0.23)
        figure.text(0.14, 0.985, "Movies · DeepSeek-V4-Pro", va="top", fontsize=7.0, color="#0b0b0b")
        bars = {}
        for ax, panel, conditions, positions, title in (
                (axes[0], "identifier", "OWSF", [0, 1, 2, 3.6], "(a) Missing identifier\nmapping"),
                (axes[1], "year", "OWS", [0, 1, 2], "(b) Year candidates\nretained unchanged")):
            selected = {r["condition"]: r for r in rows if r["panel"] == panel}
            bars[panel] = list(ax.bar(positions, [selected[c]["repair_fraction"] * 100 for c in conditions],
                                     width=0.65, color=[color[c] for c in conditions], linewidth=0, zorder=3))
            for x, condition in zip(positions, conditions):
                row = selected[condition]
                ax.text(x, row["repair_fraction"] * 100 + 4, f'{row["repaired"]}/{row["errors"]}',
                        ha="center", va="bottom", color="#0b0b0b", fontsize=6.0)
            ax.set_xticks(positions, list(conditions))
            ax.set_ylim(0, 115)
            ax.set_yticks([0, 50, 100], ["0", "50", "100"])
            ax.set_title(title, loc="left", pad=4, linespacing=1.12)
            ax.grid(axis="y", color="#e1e0d9", linewidth=0.5, zorder=0)
            ax.tick_params(axis="both", length=2, width=0.5, pad=2)
            ax.set_axisbelow(True)
        axes[0].set_xlim(-0.6, 4.05)
        axes[1].set_xlim(-0.65, 2.65)
        axes[0].set_ylabel("Repaired (%)", labelpad=3)
        axes[1].tick_params(axis="y", left=False)
        axes[1].spines["left"].set_visible(False)
        axes[0].axvline(2.8, color="#c3c2b7", linewidth=0.6, linestyle=(0, (2, 2)))
        axes[0].text(1, -0.23, "Paired O/W/S", transform=axes[0].get_xaxis_transform(),
                     ha="center", va="top", fontsize=5.7, color="#52514e")
        axes[0].text(3.6, -0.23, "F: nonpaired", transform=axes[0].get_xaxis_transform(),
                     ha="center", va="top", fontsize=5.7, color="#52514e")
        axes[1].text(1, -0.23, "Paired O/W/S", transform=axes[1].get_xaxis_transform(),
                     ha="center", va="top", fontsize=5.7, color="#52514e")
        rule_line = axes[1].axhline(167 / 190 * 100, color="#52514e", linewidth=0.8,
                                   linestyle=(0, (3, 2)), zorder=4)
        figure.text(0.985, 0.025, "Middle-year rule: 167/190", ha="right", va="bottom",
                    fontsize=6.0, color="#52514e")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {extension: output_dir / f"{NAME}.{extension}" for extension in ("pdf", "png", "svg", "csv")}
        for extension in ("pdf", "png", "svg"):
            # No tight crop: the PDF remains exactly 3.33 × 1.65 inches in print.
            figure.savefig(paths[extension], dpi=600)
        with paths["csv"].open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return RecoveryFigure(figure, tuple(axes), rows, bars, rule_line, paths)
