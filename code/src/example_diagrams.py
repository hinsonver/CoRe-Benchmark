"""Worked examples for CoRe, using frozen cells rather than new measurements.

Run ``python -m src.example_diagrams --output-dir PATH`` for PDF/PNG/SVG/CSV.
Rows in CSV use zero-based source indices; arrows illustrate only their local test.
"""
import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyArrowPatch, Rectangle

from .data import ROOT, load

COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']
INK, MUTED, GRID = '#17212b', '#485563', '#ccd3da'
STYLE = {'font.family': 'sans-serif', 'font.sans-serif': ['DejaVu Sans'],
         'font.size': 7, 'pdf.fonttype': 42, 'svg.fonttype': 'none', 'figure.facecolor': 'white'}


@dataclass
class Diagram:
    figure: object
    axes: list
    arrows: list
    rows: list


def _row(panel, dataset, row, field, condition='', external='', note=''):
    dirty, reference = load(dataset)
    return dict(panel=panel, dataset=dataset, row=row, field=field, condition=condition,
                dirty=dirty.at[row, field], reference=reference.at[row, field],
                external=external, note=note)


def overview_rows():
    # Only the eight author-selected cells shown in the adopted manuscript are
    # included. This illustration is not a Movie-record or saved-reply replay.
    source = Path(__file__).resolve().parents[1] / 'config/diagram_examples.json'
    config = json.loads(source.read_text())
    rows = config['overview']
    if config['schema'] != 1 or len(rows) != 8:
        raise ValueError('expected eight explicit author illustration cells')
    return rows


def construction_rows():
    rows = []
    for condition, dataset, index in [('O', 'hospital', 3), ('W', 'hospital_surrogatewords', 3),
                                       ('S', 'hospital_surrogate', 3), ('F', 'hospital_fresh', 19)]:
        row = _row('construction', dataset, index, 'City', condition,
                   note='Newer record; not paired entity/row' if condition == 'F' else 'Paired row and error cell')
        row['hospital_name'] = load(dataset)[1].at[index, 'HospitalName']
        rows.append(row)
    return rows


def _axes(fig, bounds, face='white', edge=GRID):
    ax = fig.add_axes(bounds)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.add_patch(Rectangle((.003, .003), .994, .994, facecolor=face, edgecolor=edge, linewidth=.65))
    return ax


def _text(ax, x, y, value, *, size=7, bold=False, color=INK, **kwargs):
    return ax.text(x, y, value, fontsize=size, fontweight='bold' if bold else 'normal',
                   color=color, va='center', linespacing=1.14, **kwargs)


def _line(ax, y, x0=.035, x1=.965):
    ax.plot([x0, x1], [y, y], color=GRID, linewidth=.5)


def _arrow(ax, start, end, label, arrows):
    arrow = FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=6.5,
                            linewidth=.85, color=MUTED, shrinkA=0, shrinkB=0)
    arrow.set_gid(label)
    ax.add_patch(arrow)
    arrows.append(arrow)
    return arrow


def _export(result, directory, stem):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for extension in ('pdf', 'svg', 'png'):
        result.figure.savefig(directory / f'{stem}.{extension}', dpi=600, facecolor='white')
    with (directory / f'{stem}.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result.rows[0]))
        writer.writeheader()
        writer.writerows(result.rows)
    return result


def render_overview(output_dir, colors=COLORS):
    """Three separate tests, each with its own example and local arrows only."""
    rows, arrows = overview_rows(), []
    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(7.1, 2.1))
        axes = [_axes(fig, [x, .012, .324, .976]) for x in [.004, .338, .672]]
        for ax, title, fill in zip(axes, ['Recovery evidence', 'Assigned values', 'Repair credit'],
                                   ['#eaf2fc', '#edf6f1', '#fff5dc']):
            ax.add_patch(Rectangle((.003, .884), .994, .113, facecolor=fill, edgecolor='none'))
            _text(ax, .04, .94, title, bold=True, size=8)

        ax = axes[0]
        _text(ax, .04, .827, 'Movies: American Ultra (2015)', bold=True)
        _text(ax, .04, .728, 'O: public identity mapping', color=colors[0])
        _text(ax, .04, .647, 'american_ultra')
        _text(ax, .60, .647, 'tt3316948', bold=True)
        _arrow(ax, (.51, .647), (.58, .647), 'public identity mapping', arrows)
        _text(ax, .04, .538, 'W: renamed, arbitrary reference ID', color='#167a56')
        _text(ax, .04, .456, 'mill_brook')
        _text(ax, .60, .456, 'tt1095783')
        # A crossed mapping marks missing recovery evidence, not an execution step.
        ax.plot([.51, .58], [.456, .456], color=MUTED, linewidth=.8)
        ax.plot([.54, .56], [.438, .474], color='#9f3930', linewidth=1)
        _text(ax, .04, .356, 'W / S: mapping unavailable', bold=True)
        ax.add_patch(Rectangle((.025, .207), .95, .106, facecolor='#f0f3f6', edgecolor='none'))
        _text(ax, .05, .259, 'O / W / S year: 2014 2015 2016')
        _line(ax, .177)
        _text(ax, .04, .124, 'Four-condition recovery comparison', size=6.8)
        _text(ax, .04, .052, '+ independent continuation probe', size=6.8)

        ax = axes[1]
        _text(ax, .04, .827, 'Movies conflict test: Taken', bold=True)
        _text(ax, .04, .727, 'Table', bold=True, color=MUTED)
        _text(ax, .39, .727, 'Director', bold=True, color=MUTED)
        _line(ax, .684)
        for y, label in [(.623, 'Dirty'), (.525, 'Reference')]:
            _text(ax, .04, y, label)
            ax.add_patch(Rectangle((.37, y - .037), .59, .076, facecolor='#e8f4ed', edgecolor='none'))
            _text(ax, .39, y, 'Stanley Kubrick', bold=True)
        _text(ax, .04, .414, 'Schematic counting event', color=MUTED, size=6.8)
        _arrow(ax, (.54, .379), (.54, .307), 'rewrite to real-world director', arrows)
        _text(ax, .04, .248, 'Real credit:')
        _text(ax, .47, .248, 'Pierre Morel', bold=True, color='#167a56')
        _line(ax, .177)
        _text(ax, .04, .124, 'Separate knowledge-conflict test', size=6.8)
        _text(ax, .04, .052, 'Count rewrites of assigned values', size=6.8)

        ax = axes[2]
        _text(ax, .04, .827, 'Rayyan: ISSN field (row 120)', bold=True)
        _text(ax, .04, .725, 'Dirty')
        _text(ax, .49, .725, 'Mar-22', bold=True)
        _arrow(ax, (.68, .687), (.68, .611), 'recorded external-matching edit', arrows)
        _text(ax, .04, .569, 'Saved match')
        ax.add_patch(Rectangle((.465, .532), .49, .074, facecolor='#e8f4ed', edgecolor='none'))
        _text(ax, .49, .569, '0003-3022', bold=True, color='#167a56')
        _text(ax, .04, .467, 'PMID 8916815; recorded edit', size=6.8, color=MUTED)
        _line(ax, .412)
        _text(ax, .04, .345, 'Reference')
        _text(ax, .49, .345, '22-Mar', bold=True, color='#9f3930')
        _text(ax, .04, .248, 'No reference credit', bold=True, color='#9f3930')
        _line(ax, .177)
        _text(ax, .04, .124, 'Separate field / scoring checks', size=6.8)
        _text(ax, .04, .052, 'External match differs from reference', size=6.8)
        return _export(Diagram(fig, axes, arrows, rows), output_dir, 'fig0_overview')


def _city(ax, x, y, value, dirty=False):
    """Highlight only the corrupted x characters; retain each exact source value."""
    # Monospace widths are measured from the active renderer, so parts never collide.
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    point = ax.transData.transform((x, y))
    for index, char in enumerate(value):
        highlighted = dirty and char == 'x'
        text = _text(ax, x, y, char, bold=highlighted, color='#9f3930' if highlighted else INK,
                     fontfamily='DejaVu Sans Mono',
                     bbox=dict(facecolor='#ffe3b5', edgecolor='none', pad=.1) if highlighted else None)
        width = text.get_window_extent(renderer).width
        point[0] += width
        x = ax.transData.inverted().transform(point)[0]


def render_construction(output_dir, colors=COLORS):
    """Frozen Hospital rows show character corruption, not cleaner predictions."""
    rows, arrows, axes = construction_rows(), [], []
    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(7.1, 1.25))
        paired = fig.add_axes([.006, .84, .73, .15])
        fresh = fig.add_axes([.764, .84, .23, .15])
        for ax in [paired, fresh]:
            ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
        _text(paired, .005, .5, 'Paired O / W / S: same row and error cell', bold=True)
        _text(fresh, .01, .5, 'F: newer record', bold=True)
        axes.extend([paired, fresh])
        labels = ['O: original', 'W: words', 'S: syllables', 'F: fresh']
        for index, (x, row, label, color) in enumerate(zip([.006, .251, .496, .764], rows, labels,
                                                           [colors[0], colors[2], colors[3], colors[1]])):
            ax = _axes(fig, [x, .155, .23, .675], face=to_rgba(color, .065), edge=color)
            axes.append(ax)
            _text(ax, .035, .90, label, bold=True, color=color)
            _text(ax, .965, .90, f"row {row['row']}", ha='right', size=6.8, color=MUTED)
            _line(ax, .797)
            name = '\n'.join(textwrap.wrap(row['hospital_name'], width=27))
            _text(ax, .035, .640, name, size=6.8)
            _line(ax, .460)
            _text(ax, .035, .349, 'City reference', size=6.8, color=MUTED)
            _text(ax, .625, .349, 'dirty', size=6.8, color=MUTED)
            _city(ax, .035, .162, row['reference'])
            _city(ax, .625, .162, row['dirty'], dirty=True)
            _arrow(ax, (.53, .162), (.60, .162), 'character corruption', arrows)
        footer = fig.add_axes([.006, .002, .988, .145])
        footer.set_xlim(0, 1); footer.set_ylim(0, 1); footer.axis('off')
        axes.append(footer)
        _text(footer, .003, .52, 'Names change; original error positions are retained in W / S.', size=6.8)
        _text(footer, .77, .52, 'not row-paired with O', size=6.8, color=MUTED)
        return _export(Diagram(fig, axes, arrows, rows), output_dir, 'fig_example_transfer')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'figures')
    args = parser.parse_args()
    for render in [render_overview, render_construction]:
        result = render(args.output_dir)
        plt.close(result.figure)
        print(render.__name__, args.output_dir)
