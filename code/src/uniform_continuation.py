"""Hash-bound aggregate continuation reanalysis for current presentation only.

Original archives, original source bindings and frozen presentation are not changed.
No raw Movie values or model replies are read by this public aggregate projection.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from .core_runtime import check_payload, is_movie_path, root_path

DERIVED = 'results/derived/uniform_continuation.json'
DERIVED_SHA256 = 'a7c5bf2be91212a075b33a3b322ee333d029e1e2f9d9a63ba4ab3252a3fe4c9b'
MODELS = {
    'custom:deepseek/deepseek-v4-pro': 'custom_deepseek_deepseek-v4-pro',
    'local:mlx-community/OLMo-2-1124-7B-Instruct-4bit': 'local_mlx-community_OLMo-2-1124-7B-Instruct-4bit',
    'localbase:allenai/OLMo-2-1124-7B': 'localbase',
    'local:qwen2.5-7b': 'local_qwen2.5-7b',
    'local:llama3.1-8b': 'local_llama3.1-8b',
    'local:qwen2.5-14b': 'local_qwen2.5-14b',
    'local:qwen2.5-32b-awq': 'local_qwen2.5-32b-awq',
}
MODES = [('clean', False, False), ('dirty', False, False),
         ('clean', True, False), ('dirty', True, False), ('dirty', False, True)]


def verify_source(root, relative, expected):
    """Verify present bytes or the unchanged original private-source binding."""
    root = Path(root)
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe continuation source path')
    source = root / rel
    if source.is_symlink():
        raise ValueError('Continuation source symlink forbidden')
    if source.is_file():
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Continuation source hash mismatch: ' + relative)
    elif is_movie_path(relative):
        sources = json.loads((root / 'data/manifests/CORE_SOURCES.json').read_text())
        if sources['private_files'].get(relative) != expected:
            raise ValueError('Continuation private source hash mismatch: ' + relative)
    else:
        raise FileNotFoundError(source)


def _scope(model):
    datasets = ['beers', 'flights', 'hospital', 'rayyan', 'tax']
    modes = MODES[:2]
    if model.startswith('custom:'):
        datasets.append('movies_1')
        modes = MODES[:4]
    elif not model.startswith('localbase:'):
        modes = MODES if 'OLMo' not in model else [MODES[0], MODES[1], MODES[4]]
        if 'OLMo' not in model:
            datasets.append('movies_1')
    return {(ds, *mode) for ds in datasets for mode in modes
            if not ('OLMo' in model and ds == 'rayyan' and mode[2])}


def load_uniform(root=None, *, data_path=None):
    root = Path(root or root_path())
    data = Path(data_path or root / DERIVED).read_bytes()
    if hashlib.sha256(data).hexdigest() != DERIVED_SHA256:
        raise ValueError('Uniform continuation derivative hash mismatch')
    binding = json.loads((root / 'data/manifests/UNIFORM_CONTINUATION.json').read_text())
    if binding.get('files', {}).get(DERIVED) != DERIVED_SHA256:
        raise ValueError('Uniform continuation binding hash mismatch')
    value = json.loads(data)
    check_payload(value)
    if value['schema_version'] != 1 or value['method']['criterion'] != 'current_full':
        raise ValueError('Unsupported uniform continuation definition')
    if binding['provenance'] != value['provenance']:
        raise ValueError('Uniform continuation provenance mismatch')
    coverage = {model: set() for model in MODELS}
    archives = set()
    trials = 0
    for record in value['archives']:
        summary, counts = record['summary'], record['counts']
        model = summary['model']
        if model not in coverage:
            raise ValueError('Unexpected continuation model')
        setting = (summary['dataset'], summary['source'], summary['named'], summary['error_rows'])
        if setting in coverage[model] or record['archive'] in archives:
            raise ValueError('Duplicate continuation archive/setting')
        coverage[model].add(setting)
        archives.add(record['archive'])
        verify_source(root, record['archive'], record['archive_sha256'])
        if counts['parsed'] + counts['failed'] + counts['unparseable'] != summary['n']:
            raise ValueError('Continuation trial denominator mismatch')
        for key in ('inf', 'noninf', 'hard', 'leak', 'leak_hard'):
            numerator, denominator = counts[key]
            if not all(type(n) is int and n >= 0 for n in (numerator, denominator)) or numerator > denominator:
                raise ValueError('Invalid continuation integer counts')
        numerator, denominator = counts['hard']
        if summary['hard_cells'] != denominator or summary['acc_hard'] != (round(numerator / denominator, 4) if denominator else None):
            raise ValueError('Continuation summary disagrees with exact counts')
        if sum(c['n'] for c in record['per_column_integer_counts'].values()) != counts['noninf'][1]:
            raise ValueError('Continuation per-column denominator mismatch')
        trials += summary['n']
    if len(archives) != 168 or value['archive_count'] != 168 or trials != value['trials'] or trials != 9600:
        raise ValueError('Incomplete continuation coverage')
    if any(coverage[model] != _scope(model) for model in MODELS):
        raise ValueError('Incomplete continuation model/setting coverage')
    for relative, expected in value['source_tables'].items():
        verify_source(root, relative, expected)
    return value


def current_rows(root=None):
    """Select dataset maxima and pool leakage from exact per-archive integers."""
    value = load_uniform(root)
    rows = {}
    for model, tag in MODELS.items():
        records = [a for a in value['archives'] if a['summary']['model'] == model]
        best, argmax = [], []
        for source, named, errors in MODES:
            candidates = [a for a in records
                          if (a['summary']['source'], a['summary']['named'], a['summary']['error_rows']) == (source, named, errors)
                          and a['counts']['hard'][1]]
            selected = max(candidates, key=lambda a: Fraction(*a['counts']['hard'])) if candidates else None
            best.append(selected['counts']['hard'] if selected else None)
            argmax.append(selected['archive'] if selected else None)
        dirty = [a for a in records if a['summary']['source'] == 'dirty']
        leakage = [sum(a['counts']['leak_hard'][index] for a in dirty) for index in (0, 1)]
        rows[tag] = {'display': [f'{counts[0] / counts[1]:.3f}' if counts else '---' for counts in best],
                     'max_counts': best, 'argmax_archives': argmax, 'hard_leak': leakage}
    return rows
