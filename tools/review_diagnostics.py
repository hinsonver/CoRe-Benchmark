"""Offline replay of the bounded review diagnostics; never runs model clients.

Hospital profiles, seed effects, the frozen 40-comparison family and its two
GLM sensitivity changes are recomputed from included tables/count witnesses.
Truncation indices, RatingCount proposal details and historical usage are bound
aggregate evidence, not a claim to reread omitted Movie replies or usage logs.
The 184 historical source bindings remain provenance, not package membership.
"""
import argparse
import ast
import collections
import csv
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = 'results/derived/review_diagnostics.json'
AGGREGATE_SHA256 = 'f29316b0f90fd0e43345f1ad80a4fbb3c9e48c952748e95d42fcde3377192e34'
sys.path.insert(0, str(ROOT / 'code'))
from src import core_runtime as runtime


def pure_definitions(root):
    """Load only named pure definitions/literals, without importing scorers/clients."""
    namespace = {'random': random, 'G': 'identity'}
    selections = {
        'probe_clean.py': {'IDENTITY', 'metrics', 'total', 'f1_of', 'bootstrap_diff'},
        'paper_tables.py': {'COMMERCIAL', 'OPEN', 'CONDS', 'Family', 'holm'},
    }
    for filename, names in selections.items():
        source = root / 'code/src' / filename
        selected, found = [], set()
        for node in ast.parse(source.read_text()).body:
            name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in names:
                    ast.literal_eval(node.value)
            if name in names:
                selected.append(node)
                found.add(name)
        if found != names:
            raise ValueError('Missing pure replay definitions: ' + filename)
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace


class Diagnostics:
    def __init__(self, root, evidence, witnesses):
        self.root, self.evidence, self.witnesses = root, evidence, witnesses
        self.ns, self.cache = pure_definitions(root), {}
        self.models = self.ns['COMMERCIAL'] + self.ns['OPEN']

    def chunks(self, tag, condition):
        key = tag, condition
        if key not in self.cache:
            name = self.root / 'artifacts/raw_outputs/p2' / f'{tag}__{condition}__k20__spread.json'
            self.cache[key] = runtime.evidence_json(name, self.root)['chunks']
        return self.cache[key]

    @staticmethod
    def seeded(condition, seed):
        return condition if seed == 0 else f'{condition}_s{seed}'

    def hospital(self):
        def profile(condition):
            directory = self.root / 'data/final' / condition
            with (directory / 'clean.csv').open(newline='') as handle:
                reader = csv.reader(handle)
                header, clean = next(reader), list(reader)
            with (directory / 'dirty.csv').open(newline='') as handle:
                reader = csv.reader(handle)
                next(reader)
                dirty = list(reader)
            if len(dirty) != len(clean) or any(len(row) != len(header) for row in dirty + clean):
                raise ValueError('Hospital source shape mismatch')
            columns = [header.index(name) for name in self.ns['IDENTITY']['hospital']]
            mask = {(i, col) for i, (d, c) in enumerate(zip(dirty, clean)) for col in columns if d[col] != c[col]}
            histogram = collections.Counter(sum(a != b for a, b in zip(dirty[i][col], clean[i][col]))
                                            for i, col in mask if len(dirty[i][col]) == len(clean[i][col]))
            bins = [histogram[1], histogram[2], sum(v for k, v in histogram.items() if k >= 3)]
            return {'errors': len(mask), 'character_distribution': {str(k): v for k, v in sorted(histogram.items())},
                    'bins_1_2_3plus': bins, 'fractions': [v / sum(bins) for v in bins],
                    'validator_rounded_fractions': [round(v / sum(bins), 3) for v in bins]}, mask
        original, mask = profile('hospital')
        words = []
        for seed in range(3):
            row, other = profile(self.seeded('hospital_surrogatewords', seed))
            row.update(seed=seed, mask_equal_original=mask == other,
                       max_abs_gap_pp=100 * max(abs(x - y) for x, y in zip(row['fractions'], original['fractions'])),
                       passes_8pp=all(abs(x - y) <= .08 for x, y in zip(row['validator_rounded_fractions'], original['validator_rounded_fractions'])))
            words.append(row)
        return {'original': original, 'words': words, 'tolerance_pp': 8,
                'character_count_is_not_model_difficulty': True}

    def seed_effects(self):
        rows, f1 = [], self.ns['f1_of']
        for tag, name in self.models:
            for dataset in ('hospital', 'movies'):
                conditions = self.ns['CONDS'][dataset]
                values = {'O': f1(self.chunks(tag, conditions[0]), 'identity')}
                for label, condition in zip('FWS', conditions[1:]):
                    values[label] = [f1(self.chunks(tag, self.seeded(condition, seed)), 'identity') for seed in range(3)]
                effects = {'O-W': [values['O'] - v for v in values['W']],
                           'F-W': [a-b for a, b in zip(values['F'], values['W'])],
                           'W-S': [a-b for a, b in zip(values['W'], values['S'])],
                           'O-S': [values['O'] - v for v in values['S']]}
                rows.append({'model': name, 'dataset': dataset, 'f1': values, 'effects': effects,
                             'seed1_2_ranges': {k: [min(v[1:]), max(v[1:])] for k, v in effects.items()}})
        return rows

    def truncation(self):
        saved = self.evidence['truncation']
        tag, observed, total = 'custom_z-ai_glm-5.3', {}, 0
        conditions = ['movies'] + [self.seeded(c, s) for c in self.ns['CONDS']['movies'][1:] for s in range(3)]
        for condition in conditions:
            chunks = self.chunks(tag, condition)
            total += len(chunks)
            indices = [i+1 for i, chunk in enumerate(chunks) if chunk['truncated']]
            if indices:
                observed[condition] = indices
        if observed != saved['truncated'] or total != saved['chunks'] or len(conditions) != saved['tables']:
            raise ValueError('GLM aggregate indices disagree with anonymous witness flags')
        return saved

    def families(self):
        original, sensitivity, family = [], [], self.ns['Family']()
        excluded = self.evidence['truncation']['truncated']
        for tag, name in self.models:
            for dataset, contrasts in (('hospital', ('F-W', 'W-S', 'O-S')), ('movies', ('F-W', 'O-W'))):
                conditions = dict(zip('OFWS', self.ns['CONDS'][dataset]))
                for contrast in contrasts:
                    left, right = (conditions[c] for c in contrast.split('-'))
                    a, b = self.chunks(tag, left), self.chunks(tag, right)
                    paired = contrast != 'F-W'
                    position = len(original)
                    def calculate(a, b):
                        family.add(a, b, paired, n=2000, seed=0)
                        _, lo, hi = self.ns['bootstrap_diff'](a, b, 'identity', paired, n=2000, seed=0)
                        return {'position': position, 'model': name, 'dataset': dataset, 'contrast': contrast,
                                'paired': paired, 'n': [len(a), len(b)], 'diff': family.items[-1][1],
                                'ci95': [lo, hi], 'mc_p': family.items[-1][2]}
                    row = calculate(a, b)
                    original.append(row)
                    if tag == 'custom_z-ai_glm-5.3' and dataset == 'movies':
                        if paired:
                            if [x['rows'] for x in a] != [x['rows'] for x in b]:
                                raise ValueError('Paired Movie witnesses no longer share chunk rows')
                            remove = set(excluded.get(left, [])) | set(excluded.get(right, []))
                            a, b = ([chunk for i, chunk in enumerate(side, 1) if i not in remove] for side in (a, b))
                        else:
                            a, b = ([chunk for i, chunk in enumerate(side, 1) if i not in excluded.get(condition, [])]
                                    for side, condition in ((a, left), (b, right)))
                        sensitivity.append(calculate(a, b))
                    else:
                        sensitivity.append(dict(row))
        for rows in (original, sensitivity):
            for row, adjusted in zip(rows, self.ns['holm']([r['mc_p'] for r in rows])):
                row['holm_p'] = adjusted
        return {'original': original, 'sensitivity': sensitivity,
                'parameters': self.evidence['families']['parameters']}

    def rayyan(self):
        source = json.loads((self.root / 'results/derived/rayyan_audit.json').read_text())
        strata = []
        for name in ('日期', '编码乱码', '缺失写成-1', '页码', 'ISSN'):
            rows = [row for row in source if row['stratum'] == name]
            matched = [row for row in rows if row.get('pmid')]
            strata.append({'stratum': name, 'sampled': len(rows), 'matched': len(matched),
                           'match_fraction': len(matched)/len(rows),
                           'reference_agrees': sum(row['clean_ok'] for row in matched),
                           'dirty_agrees': sum(row['dirty_ok'] for row in matched)})
        return {'sampled': len(source), 'matched': sum(row['matched'] for row in strata),
                'strata': strata, 'scope': 'archived matches only; no new truth or unmatched imputation'}

    def aggregate_consistency(self):
        for row, condition in zip(self.evidence['rating_count']['conditions'], self.ns['CONDS']['movies']):
            counts = self.witnesses['views']['movies_columns'][condition]['RatingCount']
            if any(row[k] != counts[k] for k in ('errors', 'repaired')):
                raise ValueError('RatingCount aggregate differs from column-count witness')
            if (row['effective_edits'] != row['repaired'] + row['wrong_edit_on_error'] + row['correct_cell_modified'] or
                    row['errors'] != row['repaired'] + row['wrong_edit_on_error'] + row['error_cells_without_effective_edit'] or
                    row['repaired'] != sum(chunk['repaired'] for chunk in row['repair_chunks']) or
                    row['raw_proposals'] < row['valid_proposals'] or
                    row['valid_proposals'] < row['noops'] + row['effective_edits'] or
                    row['repaired_by_comma_deletion'] > row['repaired']):
                raise ValueError('RatingCount aggregate is internally inconsistent')
        usage = self.evidence['usage']
        if any(usage['totals'][k] != sum(row[k] for row in usage['models']) for k in usage['totals']):
            raise ValueError('Usage aggregate totals disagree')
        for row in [usage['totals'], *usage['models']]:
            if row['input_plus_output'] != row['input'] + row['output'] or row['reasoning_included_in_output'] > row['output']:
                raise ValueError('Usage aggregate double counts reasoning or totals')


def replay(root=ROOT, *, aggregate_path=None):
    root = Path(root).resolve()
    path = Path(aggregate_path) if aggregate_path is not None else root / AGGREGATE
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != AGGREGATE_SHA256:
        raise ValueError('Review aggregate hash mismatch')
    aggregate = json.loads(raw)
    if aggregate['schema'] != 'second-review-aggregate-v1':
        raise ValueError('Unsupported review aggregate schema')
    witnesses = runtime.read_witnesses(root)  # Mandatory, checked before any replay.
    if not runtime.public_mode():
        raise ValueError('Review diagnostics require public statistical witness mode')
    audit = Diagnostics(root, aggregate['evidence'], witnesses)
    results = {name: getattr(audit, name)() for name in ('hospital', 'seed_effects', 'truncation', 'families', 'rayyan')}
    for name, result in results.items():
        if result != aggregate['evidence'][name]:
            raise ValueError('Review replay differs from bound aggregate: ' + name)
    audit.aggregate_consistency()
    changed = [i for i, (a, b) in enumerate(zip(results['families']['original'], results['families']['sensitivity'])) if a != b]
    if changed != [13, 14]:
        raise ValueError('Frozen 40-comparison sensitivity scope changed')
    results['families']['changed_positions'] = changed
    for row in results['rayyan']['strata']:
        row['dirty_assessment'] = 'unassessed' if row['stratum'] == '编码乱码' else 'assessed'
        row['dirty_agrees_assessed'] = None if row['dirty_assessment'] == 'unassessed' else row['dirty_agrees']
    return {'status': 'PASS', 'aggregate_sha256': AGGREGATE_SHA256,
            'capability': {'raw_movie_reply_rescoring': False, 'usage_log_replay': False,
                           'truncation_detection_replayed': False, 'historical_source_bindings_checked': False,
                           'anonymous_chunk_counts_replayed': True, 'hospital_table_profiles_replayed': True},
            'scope': {'recomputed': ['hospital', 'seed_effects', 'families', 'rayyan'],
                      'aggregate_only_with_consistency_checks': ['rating_count', 'usage'],
                      'bound_indices_checked_against_witness_flags': ['truncation'],
                      'source_sha256': 'historical provenance only; original sources are not all packaged',
                      'new_model_calls': 0},
            'aggregate_only': {name: aggregate['evidence'][name] for name in ('rating_count', 'usage')},
            **results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay(args.root)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        with args.output.open('x') as handle:
            handle.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
