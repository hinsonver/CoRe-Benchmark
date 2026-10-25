"""Checked display projections for the SG revision; never re-score evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re

CONFIG = Path(__file__).resolve().parents[1] / 'config/paper_presentation.json'

_MODEL_HEADER = r'    Model & O & F & W & S & F$-$W & W$-$S & O$-$S & O & F & W & S & F$-$W & O$-$W \\'
_GROUPED_HEADER = r'''    & \multicolumn{4}{c}{Scores} & Nonpaired & \multicolumn{2}{c}{Paired} & \multicolumn{4}{c}{Scores} & Nonpaired & Paired \\
    \cmidrule(lr){2-5}\cmidrule(lr){6-6}\cmidrule(lr){7-8}\cmidrule(lr){9-12}\cmidrule(lr){13-13}\cmidrule(l){14-14}
''' + _MODEL_HEADER


def group_decomposition_header(text):
    """Group comparisons without touching a numerical or significance cell."""
    if text.count(_MODEL_HEADER) != 1:
        raise ValueError('expected exactly one recognized decomposition header')
    if _GROUPED_HEADER in text:
        return text
    return text.replace(_MODEL_HEADER, _GROUPED_HEADER, 1)


def caption_span(text):
    match = re.search(r'\\caption\{', text)
    if not match:
        raise ValueError('missing caption')
    start = match.end()
    depth, index = 1, start
    while depth and index < len(text):
        if text[index] in '{}' and text[index - 1] != '\\':
            depth += 1 if text[index] == '{' else -1
        index += 1
    if depth:
        raise ValueError('unbalanced caption')
    return start, index - 1


def project_tables(inputs):
    sources = json.loads(CONFIG.read_text())['sources']
    if set(inputs) != set(sources):
        raise ValueError('expected the 17 explicit full table sources')
    outputs = {}
    for name, spec in sources.items():
        text = inputs[name]
        start, end = caption_span(text)
        audited = text[:start] + text[end:]
        if name == 'decomposition.tex':
            audited = audited.replace(_GROUPED_HEADER, _MODEL_HEADER)
        digest = hashlib.sha256(audited.encode()).hexdigest()
        if digest != spec['body_sha256']:
            raise ValueError(f'{name}: frozen non-caption content changed')
        outputs[name] = text[:start] + spec['caption'] + text[end:]
        if name == 'decomposition.tex':
            outputs[name] = group_decomposition_header(outputs[name])

    rows = []
    for line in outputs['aligned.tex'].splitlines():
        if r'\multicolumn{5}' in line or r'\quad Baran, whole table' in line or r'\quad TabClean' in line:
            rows.append(line.replace('Baran, whole table', 'Baran'))
    outputs['whole_table.tex'] = r'''\begin{table}[tbp]
  \caption{Identity-column repair F1 with whole-table information. Baran uses perfect detection
  and is the mean of three runs. TabClean uses DeepSeek-V4-Pro with development rows excluded.}
  \label{tab:whole}
  \small
  \begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}l cccc@{}}
    \toprule
    Method & O & F & W & S \\
    \midrule
''' + '\n'.join(rows) + r'''
    \bottomrule
  \end{tabular*}
\end{table}
'''
    rows = []
    for line in outputs['rayyan.tex'].splitlines():
        fields = [x.strip() for x in line.removesuffix(r' \\').split('&')]
        if len(fields) == 6 and fields[1].isdigit():
            name, population, sampled, matched, failed, passed = fields
            dirty = '---' if passed == '---' else f'{passed}/{matched}'
            rows.append(f'    {name} & {population} & {sampled} & {matched} & {failed}/{matched} & {dirty} ' + r'\\')
    if len(rows) != 5:
        raise ValueError('expected five Rayyan strata')
    outputs['rayyan_checks.tex'] = r'''\begin{table}[tbp]
  \caption{Rayyan field checks: population $N_h$, sample $n_h$, title matches $m_h$,
  failed reference and passed dirty checks per matched cell. A dash denotes an unassessed dirty check.}
  \label{tab:rayyan}
  \small
  \setlength{\tabcolsep}{3pt}
  \begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}lrrrcc@{}}
    \toprule
    Check & $N_h$ & $n_h$ & $m_h$ & \shortstack{Reference fail\\$b_h/m_h$} & \shortstack{Dirty pass\\$d_h/m_h$} \\
    \midrule
''' + '\n'.join(rows) + r'''
    \bottomrule
  \end{tabular*}
\end{table}
'''
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-tables', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = json.loads(CONFIG.read_text())['sources']
    inputs = {name: (args.source_tables / name).read_text() for name in sources}
    outputs = project_tables(inputs)
    # New directory only: do not overwrite full sources or an accepted package.
    args.output.mkdir(parents=True, exist_ok=False)
    for name, text in outputs.items():
        (args.output / name).write_text(text)
    print(json.dumps({'full_sources': len(sources), 'compact_sources': len(outputs)-len(sources),
                      'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
