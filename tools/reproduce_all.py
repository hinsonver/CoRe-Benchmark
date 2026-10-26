"""One offline coverage run; historical agreement and submission eligibility are separate.

Only archived-data scorers and read-only experiment plans are dispatched. This
standard-library coordinator never imports model clients or reads .env. Exit 2
means technical execution completed with explicitly documented material limits;
exit 1 means an unexpected execution/verification failure, not scientific success.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'build', '__pycache__', '.venv', '.git'}
# Canonical SHA-256 of all per-archive records in the independently inspected
# public/full continuation reports, not merely mismatch totals. This binds the
# exact archive identities/hashes, trial checks, field-level discrepancy inventory
# and rejudged values. Authorization records/paths are intentionally excluded.
CONTINUATION_RECORDS_SHA256 = {
    0: '4750752506a6bd30499dfdaae269b950d14ba07f3785b0e323bc0de6f19da0d7',
    24: '74323cf343d42fa5dccada1ff81d915242c380d586c181bbbd33da6346c143b3',
}
LEGACY_BASELINE_DIFFERENCE = {
    'location': 'aligned/baran__movies_fresh/row_metadata', 'reconstructed': 0, 'archived': 19,
    'classification': 'legacy_unseeded_not_selected_for_frozen_comparison',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_output(root, output, historical_root=None):
    root = Path(root).resolve()
    candidate = Path(os.path.abspath(output))
    if any(p.is_symlink() for p in (candidate, *candidate.parents)):
        raise ValueError('Output must not contain a symlink')
    output = candidate.resolve()
    if output.exists():
        raise ValueError('Output already exists; no overwrite')
    if output == root or output in root.parents:
        raise ValueError('Output must not contain the package source')
    if root in output.parents and root / 'build' not in output.parents:
        raise ValueError('Package-local output must be below build, never a source directory')
    if historical_root is not None:
        history = Path(historical_root).resolve()
        if output == history or history in output.parents or output in history.parents:
            raise ValueError('Output must not overlap historical sources')
    return output


def verify_manifest(root):
    """Check the entire package before creating a destination or importing its code."""
    root = Path(root)
    bound = {}
    for line in (root / 'MANIFEST.sha256').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        relative = Path(name)
        if (relative.is_absolute() or '..' in relative.parts or name in bound
                or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('Unsafe or duplicate manifest member')
        path = root / relative
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Manifest symlink forbidden: ' + name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Package hash mismatch: ' + name)
        bound[name] = expected
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and not EXCLUDED.intersection(p.relative_to(root).parts)
              and p.name != 'MANIFEST.sha256'}
    if actual != set(bound):
        raise ValueError('Unmanifested or missing package members')
    return {'files': len(bound), 'sha256': digest(root / 'MANIFEST.sha256')}


def validate_matrix(matrix):
    if not isinstance(matrix, dict) or matrix.get('schema_version') != 1:
        raise ValueError('Unsupported REPRODUCTION schema')
    routes = matrix.get('routes')
    if not isinstance(routes, list) or not routes:
        raise ValueError('REPRODUCTION requires nonempty routes')
    seen = set()
    for route in routes:
        name = route.get('id') if isinstance(route, dict) else None
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError('REPRODUCTION route ids must be nonempty and unique')
        seen.add(name)
        for role in ('execution', 'scoring'):
            value = route.get(role)
            if not isinstance(value, dict) or not isinstance(value.get('command'), str) or not value['command'].strip():
                raise ValueError('REPRODUCTION route requires execution/scoring command strings')
    return matrix


def clean_environment(root, original=None):
    original = os.environ if original is None else original
    # Allowlist excludes inherited credentials, CORE redirects, PYTHONPATH and
    # provider endpoint configuration. No dotenv fallback is permitted.
    allow = {'PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'TMP', 'TEMP',
             'LANG', 'LC_ALL', 'LC_CTYPE', 'SYSTEMROOT', 'WINDIR',
             'DYLD_LIBRARY_PATH', 'LD_LIBRARY_PATH'}
    env = {key: value for key, value in original.items() if key in allow}
    env.update(CORE_MODE='public', CORE_ARTIFACT_ROOT=str(root),
               PYTHONPATH=os.pathsep.join((str(root), str(Path(root) / 'code'))),
               PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
               PYTHON=sys.executable, MPLBACKEND='Agg')
    return env


GUARD = '''"""Offline-only child-process guard, including grandchildren."""
import os
from pathlib import Path
import subprocess
import sys
import types
_guard_dir = str(Path(__file__).resolve().parent)
def _deny(*args, **kwargs):
    raise RuntimeError('Offline reproduction forbids model generation')
def _truncated(text):
    text = text.strip()
    return not text or not text.endswith(('}', '```'))
# The pure formatting helper is retained without importing the cache-reading
# client module. Every generation entry point is deliberately unavailable.
_clients = types.ModuleType('src.clients')
_clients.truncated = _truncated
_clients.complete = _deny
_clients.complete_json = _deny
sys.modules['src.clients'] = _clients
def _audit(event, args):
    if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.bind'):
        raise RuntimeError('Offline reproduction forbids network access')
    if event == 'import' and args and args[0].split('.')[0] in {
        'openai', 'anthropic', 'dotenv', 'requests', 'httpx', 'huggingface_hub',
        'transformers', 'vllm', 'mlx_lm', 'langchain_openai'}:
        raise RuntimeError('Offline reproduction forbids service/model client imports')
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        if Path(name).name.startswith('.env'):
            raise RuntimeError('Offline reproduction forbids .env reads')
sys.addaudithook(_audit)
_popen = subprocess.Popen
def _offline_popen(*args, **kwargs):
    env = dict(kwargs.get('env') or os.environ)
    parts = env.get('PYTHONPATH', '').split(os.pathsep)
    env['PYTHONPATH'] = os.pathsep.join([_guard_dir] + [p for p in parts if p and p != _guard_dir])
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONNOUSERSITE'] = '1'
    kwargs['env'] = env
    return _popen(*args, **kwargs)
subprocess.Popen = _offline_popen
'''


def write_guard(output):
    target = Path(output) / 'offline-guard'
    target.mkdir()
    (target / 'sitecustomize.py').write_text(GUARD)
    return target


def compare_products(reference, generated, pattern, expected_count):
    refs = {p.name: p for p in Path(reference).glob(pattern)}
    got = {p.name: p for p in Path(generated).glob(pattern)}
    records = []
    for name in sorted(set(refs) | set(got)):
        a, b = refs.get(name), got.get(name)
        records.append({'name': name, 'reference_sha256': digest(a) if a else None,
                        'generated_sha256': digest(b) if b else None,
                        'byte_identical': bool(a and b and a.read_bytes() == b.read_bytes())})
    inventory = len(refs) == expected_count and set(refs) == set(got)
    return {'expected_count': expected_count, 'reference_count': len(refs), 'generated_count': len(got),
            'inventory_equal': inventory, 'byte_identical': inventory and all(r['byte_identical'] for r in records),
            'files': records}


def complete_scoring_report(name, report):
    if not isinstance(report, dict) or report.get('schema_version') != 1:
        return False
    if name == 'continuations':
        records = report.get('archives')
        try:
            historical = report['historical_movie_archives']
            if historical not in CONTINUATION_RECORDS_SHA256:
                return False
            canonical = json.dumps(records, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
            return (report.get('mode') == 'saved_raw_trial_rejudgment'
                    and report.get('new_model_calls') == 0 and report.get('summary_fallback') is False
                    and report.get('raw_movie_records_exported') == 0
                    and report['included_archives'] == 144
                    and report['trials'] == (9600 if historical else 8200)
                    and report['summary_mismatch_archives'] == (12 if historical else 10)
                    and report['parsed_flag_mismatches'] == 0
                    and isinstance(records, list) and len(records) == 144 + historical
                    and len({r['archive'] for r in records}) == len(records)
                    and sum(r['trial_checks']['trials'] for r in records) == report['trials']
                    and sum(bool(r['comparison']['mismatches']) for r in records) == report['summary_mismatch_archives']
                    and all(r['trial_checks']['sampling_matches'] is True
                            and r['trial_checks']['parsed_flag_mismatches'] == 0 for r in records)
                    and hashlib.sha256(canonical).hexdigest() == CONTINUATION_RECORDS_SHA256[historical])
        except (KeyError, TypeError, ValueError):
            return False
    if name == 'baselines':
        try:
            if report['mode'] not in ('public_raw_only', 'authorized_historical'):
                return False
            historical = report['mode'] == 'authorized_historical'
            bases = ['hospital', 'beers'] + (['movies'] if historical else [])
            conditions = [c for base in bases for c in
                          ('beers_orig' if base == 'beers' else base, base + '_fresh',
                           base + '_surrogatewords', base + '_surrogate')]
            tabclean, baran, aligned = (report[k] for k in ('tabclean', 'whole_table_baran', 'aligned'))
            if not all(isinstance(v, dict) for v in (tabclean, baran, aligned)):
                return False
            # Exact E5 names come from the bound original inventory, not a report's
            # own self-declared total. This includes all construction/algorithm seeds.
            sources = json.loads((ROOT / 'data/manifests/CORE_SOURCES.json').read_text())
            e5_names = {Path(p).name for p in sources['original_files']
                        if p.startswith('artifacts/raw_outputs/e5/') and '__seed' in p
                        and p.endswith('.json') and (historical or '/movies' not in p)}
            aligned_names = {stem + '.json' for condition in conditions for stem in
                             [f'baran__{condition}'] + [f'baran__{condition}__run{k}' for k in range(3)]
                             + [f'custom_deepseek_deepseek-v4-pro__{condition}']}
            missing = {f'{dataset}__{mode}__seed{seed}.json' for dataset in ('hospital', 'beers_orig')
                       for mode in ('perfect', 'raha') for seed in range(3)}
            bad_aligned = {'baran__movies_fresh.json'} if historical else set()
            coverage = report['coverage']
            if not (set(tabclean) == set(conditions) | {'rayyan'} and set(baran) == e5_names
                    and len(baran) == (84 if historical else 54) and set(aligned) == aligned_names
                    and len(aligned) == (60 if historical else 40)
                    and coverage['tabclean_raw_conditions'] == len(tabclean) == (13 if historical else 9)
                    and coverage['e5_raw_runs'] == (72 if historical else 42)
                    and coverage['e5_count_only_runs'] == 12
                    and coverage['aligned_raw_archives'] == (59 if historical else 40)
                    and coverage['aligned_archives_inspected'] == len(aligned)
                    and set(coverage['aligned_historical_metadata_mismatches']) == bad_aligned
                    and len(coverage['aligned_historical_metadata_mismatches']) == len(bad_aligned)
                    and set(coverage['e5_missing_fixes']) == missing and len(coverage['e5_missing_fixes']) == 12):
                return False
            if not all(v['raw_verified'] is True and v['status'] == 'raw_verified' for v in tabclean.values()):
                return False
            if not all(v['raw_verified'] is (name not in missing)
                       and v['status'] == ('archived_count_only' if name in missing else 'raw_verified')
                       for name, v in baran.items()):
                return False
            if not all(v['raw_verified'] is (name not in bad_aligned)
                       and v['status'] == ('historical_row_metadata_mismatch' if name in bad_aligned else 'raw_verified')
                       for name, v in aligned.items()):
                return False
            if historical:
                legacy = aligned['baran__movies_fresh.json']
                discrepancy = legacy['metadata_discrepancy']
                if not (legacy['selected_for_frozen_comparison'] is False
                        and discrepancy['mismatched_chunks'] == 19
                        and discrepancy['unexpected_scored_rows'] == 12
                        and discrepancy['missing_scored_rows'] == 12
                        and discrepancy['frozen_comparison_uses_this_archive'] is False):
                    return False
            expected_groups = {name.rsplit('__', 2)[0] + '|' + name.rsplit('__', 2)[1] for name in e5_names}
            if (set(report['e5_summaries']) != expected_groups
                    or set(report['aligned_summaries']) != {c + '|' + g for c in conditions for g in ('all', 'identity', 'other')}):
                return False
            expected_differences = [LEGACY_BASELINE_DIFFERENCE] if historical else []
            return (report['no_generation_training_or_network_calls'] is True
                    and report['frozen_results_modified'] is False
                    and report['differences'] == expected_differences
                    and report['legacy_selection_provenance']['selected_frozen_comparison_differences'] == [])
        except (KeyError, TypeError, ValueError, OSError, AttributeError):
            return False
    return False


def expected_discrepancy(name, returncode, report):
    if not complete_scoring_report(name, report):
        return False
    if name == 'continuations':
        return returncode == 1 and bool(report['summary_mismatch_archives'] or report['parsed_flag_mismatches'])
    return name == 'baselines' and returncode == 2 and bool(report['differences'])


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def run_child(name, argv, root, output, env, report_path=None):
    logs = output / 'commands' / name
    logs.mkdir(parents=True)
    completed = subprocess.run(argv, cwd=root, env=env, text=True, capture_output=True)
    (logs / 'stdout.log').write_text(completed.stdout)
    (logs / 'stderr.log').write_text(completed.stderr)
    record = {'id': name, 'argv': argv, 'cwd': str(root), 'returncode': completed.returncode,
              'stdout': str((logs / 'stdout.log').relative_to(output)),
              'stderr': str((logs / 'stderr.log').relative_to(output)),
              'report': None, 'expected_scientific_discrepancy': False, 'execution_completed': False}
    report = None
    try:
        if report_path is not None:
            report = json.loads(report_path.read_text())
        elif completed.returncode == 0:
            # The core product generators log progress before their final JSON.
            try:
                report = json.loads(completed.stdout)
            except json.JSONDecodeError:
                report = json.loads(completed.stdout.strip().splitlines()[-1])
            report_path = logs / 'report.json'
            write_json(report_path, report)
        if report is not None:
            record['report'] = {'path': str(report_path.relative_to(output)), 'sha256': digest(report_path)}
        discrepancy = expected_discrepancy(name, completed.returncode, report)
        report_valid = complete_scoring_report(name, report) if name in ('continuations', 'baselines') else isinstance(report, dict)
        record.update(expected_scientific_discrepancy=discrepancy,
                      execution_completed=report_valid and (completed.returncode == 0 or discrepancy))
        if not record['execution_completed']:
            record['error'] = 'Unexpected child failure or missing/incomplete report'
    except (OSError, ValueError, TypeError) as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
    write_json(logs / 'command.json', record)
    return record, report


def command(code, *args):
    return [sys.executable, '-B', '-c', code, *map(str, args)]


def product_reference(root, matrix, key, fallback):
    relative = matrix.get('references', {}).get(key, fallback)
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Unsafe reference path in REPRODUCTION')
    return root / relative


def execute(root, output, historical_root=None, authorization_record=None):
    root = Path(root).resolve()
    if (historical_root is None) != (authorization_record is None):
        raise ValueError('historical-root and authorization-record must be supplied together')
    output = validate_output(root, output, historical_root)
    verified = verify_manifest(root)  # No output creation or artifact imports before this line.
    matrix = validate_matrix(json.loads((root / 'REPRODUCTION.json').read_text()))
    matrix_hash = digest(root / 'REPRODUCTION.json')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'mode': 'offline_complete_coverage',
              'source_manifest': verified, 'reproduction_sha256': matrix_hash,
              'historical_requested': historical_root is not None,
              'new_model_calls': 0, 'experiment_execution_requested': False,
              'commands': [], 'comparisons': {}, 'child_reports': {},
              'declared_routes': matrix['routes'], 'errors': []}
    try:
        guard = write_guard(output)
        env = clean_environment(root)
        env['PYTHONPATH'] = str(guard) + os.pathsep + env['PYTHONPATH']
        env['MPLCONFIGDIR'] = str(output / 'mplconfig')
        env['CORE_MPLCONFIG_DIR'] = env['MPLCONFIGDIR']
        extras = []
        if historical_root is not None:
            extras = ['--historical-root', str(Path(historical_root).resolve()),
                      '--authorization-record', str(Path(authorization_record).resolve())]
        jobs = [('package_verify', command('import json; from tools.core import verify; print(json.dumps(verify()))'), None)]
        for presentation in ('current', 'frozen'):
            jobs.append((presentation + '_products', command(
                'import json,sys; from pathlib import Path; from tools.core import run_products; '
                'print(json.dumps(run_products(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3])))',
                root, output / presentation, presentation), None))
        jobs.append(('continuations', [sys.executable, '-B', str(root / 'tools/score_continuations.py'),
                                      '--root', str(root), '--output', str(output / 'continuations'), *extras],
                     output / 'continuations/continuation-scores.json'))
        jobs.append(('baselines', command(
            'import json,sys; from pathlib import Path; from tools.score_baselines import replay,write_report; '
            'r=replay(Path(sys.argv[1]),Path(sys.argv[3]) if len(sys.argv)>3 else None,'
            'Path(sys.argv[4]) if len(sys.argv)>4 else None); write_report(Path(sys.argv[2]),r); '
            'print(json.dumps({"status":r["status"]})); sys.exit(2 if r["differences"] else 0)',
            root, output / 'baselines', *([Path(historical_root).resolve(), Path(authorization_record).resolve()]
                                         if historical_root is not None else [])), output / 'baselines/baseline-scores.json'))
        for name, path in (('rayyan', 'tools/check_rayyan.py'), ('screening', 'tools/check_screening.py'),
                           ('beers_provenance', 'supplements/beers-f-input-provenance/verify.py')):
            jobs.append((name, [sys.executable, '-B', str(root / path)], None))
        jobs.append(('diagnostics', [sys.executable, '-B', str(root / 'tools/review_diagnostics.py'),
                                     '--root', str(root), '--output', str(output / 'diagnostics.json')],
                     output / 'diagnostics.json'))
        # Exercise every execution-route planner without importing model clients,
        # dependency preflights, generating outputs, or taking strings as shell code.
        jobs.append(('execution_plans', command(
            'import json; from tools.experiments import parser,make_plan; '
            'routes=("cleaning","continuation","conflicts","aligned-llm","aligned-baran","baran","tabclean","rayyan-retrieval"); '
            'plans=[make_plan(parser().parse_args(["--plan","--experiment",r,"--dataset",'
            '("rayyan" if r=="rayyan-retrieval" else "hospital")]+ '
            '([] if r in ("baran","aligned-baran","rayyan-retrieval") else '
            '["--model","custom:deepseek/deepseek-v4-pro"]))) for r in routes]; '
            'print(json.dumps({"new_model_calls":0,"plans":plans,"execution_performed":False}))'), None))
        if historical_root is not None:
            jobs.append(('exact_movies_witnesses', command(
                'import json,sys; from pathlib import Path; from tools.core import validate_private; '
                'print(json.dumps(validate_private(*map(Path,sys.argv[1:]))))', root,
                Path(historical_root).resolve(), Path(authorization_record).resolve(), output / 'exact-movies'), None))
        for name, argv, child_path in jobs:
            record, child = run_child(name, argv, root, output, env, child_path)
            report['commands'].append(record)
            if child is not None:
                report['child_reports'][name] = record['report']
            if not record['execution_completed']:
                report['errors'].append(name + ': ' + record.get('error', 'unexpected failure'))
        for name, ref, got, pattern, count in (
                ('current_tables', product_reference(root, matrix, 'current_tables', 'paper/latex/tables'), output / 'current/tables', '*.tex', 19),
                ('current_figure_csvs', product_reference(root, matrix, 'current_csvs', 'results/figures'), output / 'current/figures', '*.csv', 11),
                ('frozen_tables', product_reference(root, matrix, 'frozen_tables', 'data/reference/frozen-tables'), output / 'frozen/tables', '*.tex', 15)):
            comparison = compare_products(ref, got, pattern, count)
            report['comparisons'][name] = comparison
            if not comparison['byte_identical']:
                report['errors'].append(name + ': generated/reference byte comparison failed')
        # A final manifest pass catches accidental source mutation by any child.
        report['source_manifest_after'] = verify_manifest(root)
        if report['source_manifest_after'] != verified:
            report['errors'].append('Source manifest changed during execution')
    except Exception as exc:
        report['errors'].append(type(exc).__name__ + ': ' + str(exc))
        (output / 'unexpected-error.log').write_text(traceback.format_exc())
    finalize(report, output)
    return report


def load_child(report, output, name):
    binding = report['child_reports'].get(name)
    if binding is None:
        return {}
    path = output / binding['path']
    if digest(path) != binding['sha256']:
        raise ValueError('Child report changed: ' + name)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Child report must be an object: ' + name)
    return value


def finalize(report, output):
    def checked_child(name):
        try:
            value = load_child(report, output, name)
            if value and name in ('continuations', 'baselines') and not complete_scoring_report(name, value):
                raise ValueError('Incomplete scoring report: ' + name)
            return value
        except (OSError, ValueError, TypeError, KeyError) as exc:
            report['errors'].append(name + ': ' + str(exc))
            return {}
    continuation = checked_child('continuations')
    baseline = checked_child('baselines')
    private = checked_child('exact_movies_witnesses')
    baseline_coverage = baseline.get('coverage', {})
    mismatch_fields = sum(len(r.get('comparison', {}).get('mismatches', [])) for r in continuation.get('archives', []))
    raw_agreement = (complete_scoring_report('continuations', continuation)
                     and complete_scoring_report('baselines', baseline)
                     and not continuation['summary_mismatch_archives']
                     and not continuation['parsed_flag_mismatches'] and not baseline['differences'])
    report['actual_coverage'] = {
        'continuations': {k: continuation.get(k) for k in ('included_archives', 'historical_movie_archives', 'trials',
                          'summary_mismatch_archives', 'parsed_flag_mismatches', 'legacy_schema_omission_archives')},
        'continuation_summary_mismatch_fields': mismatch_fields,
        'baselines': baseline_coverage,
        'movies_exact_witnesses': private.get('saved_reply_rescoring', {
            'p2_archives': 0, 'near_models': 0, 'p1': 'public numerical witnesses only; not raw rejudgment'}),
        'rayyan': 'version-bound local aggregate/field replay; full historical retrieval response payloads unavailable',
        'diagnostics': 'bound aggregate consistency and selected recomputation; not complete usage-log or truncation replay',
        'experiment_execution': 'eight frozen route plans inspected; no generation, retrieval, or training executed'}
    limits = [
        'Twelve whole-table Hospital/Beers Baran archives lack fixes: count-only, not raw repair validation.',
        'Complete historical Rayyan retrieval response payloads are unavailable; local replay is bounded.',
        'Historical model/API availability, third-party acquisition rights, and regenerated numerical identity are not established by offline planning.',
        'Actual reviewer access and remaining final metadata require author-side completion; no access or eligibility is inferred.']
    if not report['historical_requested']:
        limits.append('Movies raw validation not requested: default uses public numerical witnesses; exact external history and authorization are required.')
    if continuation.get('summary_mismatch_archives'):
        limits.append('Raw continuation rejudgment differs from frozen archived summaries in '
                      + str(continuation['summary_mismatch_archives']) + ' archives / ' + str(mismatch_fields)
                      + ' fields; archived numbers and current scoring are preserved separately.')
    if baseline.get('differences'):
        limits.append('Baseline scorer reports archived discrepancies, including any unselected legacy metadata exception; consult its complete report.')
    report['material_limits'] = limits
    report['technical_execution_completed'] = not report['errors'] and all(r['execution_completed'] for r in report['commands'])
    report['frozen_raw_agreement'] = bool(raw_agreement)
    report['exact_history_complete'] = False
    report['actual_review_access_ready'] = False
    report['official_eligibility'] = 'NOT_DETERMINED'
    report['exit_code'] = 1 if not report['technical_execution_completed'] else 2 if limits else 0
    report['status'] = 'completed_with_material_limits' if report['exit_code'] == 2 else 'unexpected_failure' if report['exit_code'] else 'completed_without_material_limits'
    write_json(output / 'coverage.json', report)
    lines = ['# Offline reproduction coverage', '', 'Status: ' + report['status'], '',
             '| Assessment | Outcome |', '| --- | --- |']
    for key in ('technical_execution_completed', 'frozen_raw_agreement', 'exact_history_complete',
                'actual_review_access_ready', 'official_eligibility'):
        lines.append('| ' + key + ' | ' + str(report[key]) + ' |')
    lines += ['', 'This is an offline execution/coverage record, not an official eligibility determination.', '',
              '## Actual coverage', '', '```json', json.dumps(report['actual_coverage'], ensure_ascii=False, indent=2), '```', '',
              '## Material limits', ''] + ['- ' + value for value in limits]
    lines += ['', '## Commands', '', '| Route | Exit | Execution completed | Expected discrepancy |', '| --- | --- | --- | --- |']
    lines += ['| ' + r['id'] + ' | ' + str(r['returncode']) + ' | ' + str(r['execution_completed'])
              + ' | ' + str(r['expected_scientific_discrepancy']) + ' |' for r in report['commands']]
    lines += ['', 'Command arguments, stdout/stderr, report hashes, matrix routes and every byte comparison are recorded in coverage.json and commands/.', '',
              '## Unexpected failures', ''] + (['- ' + e for e in report['errors']] or ['None.'])
    (output / 'coverage.md').write_text('\n'.join(lines) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory; never reused or overwritten')
    parser.add_argument('--historical-root', type=Path)
    parser.add_argument('--authorization-record', type=Path)
    args = parser.parse_args(argv)
    if (args.historical_root is None) != (args.authorization_record is None):
        parser.error('--historical-root and --authorization-record must be supplied together')
    try:
        result = execute(ROOT, args.output, args.historical_root, args.authorization_record)
    except (OSError, ValueError) as exc:
        print('Offline reproduction refused: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ('status', 'technical_execution_completed',
          'frozen_raw_agreement', 'exact_history_complete', 'actual_review_access_ready', 'official_eligibility', 'exit_code')}))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
