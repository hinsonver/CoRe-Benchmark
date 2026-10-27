"""Offline public statistical replay and explicit authorized historical validation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
sys.path.insert(0,str(ROOT))
from src import core_runtime as runtime


def verify(root=ROOT,release=False,release_record=None):
    root=Path(root)
    files={}
    for line in (root/'MANIFEST.sha256').read_text().splitlines():
        expected,name=line.split(maxsplit=1)
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or name in files:raise ValueError('Unsafe/duplicate package member')
        if (root/name).is_symlink() or runtime.digest(root/name)!=expected:raise ValueError('Package hash mismatch: '+name)
        files[name]=expected
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
            and not {'build','__pycache__','.venv','.git'}&set(p.relative_to(root).parts) and p.name!='MANIFEST.sha256'}
    if actual!=set(files):raise ValueError('Unmanifested or missing package members')
    if any('.git' in Path(p).parts or Path(p).name.startswith('.env') or p.endswith(('.zip','.tar','.gz','.log','.pid')) for p in actual):
        raise ValueError('Forbidden source/cache/archive member')
    sources=json.loads((root/'data/manifests/CORE_SOURCES.json').read_text())
    if any((root/p).exists() for p in sources['omitted_files']):raise ValueError('Excluded movie record member present')
    binding=json.loads((root/'data/manifests/CORE_WITNESSES.json').read_text())
    for name,expected in binding['files'].items():
        if files.get(name)!=expected:raise ValueError('Witness binding differs from package manifest')
    witnesses=runtime.read_witnesses(root)
    if set(witnesses['near'])!=set(sources['movie_near_models']):raise ValueError('Movie model coverage mismatch')
    if sources.get('publication_mode')!='statistical_core':raise ValueError('Unsupported package mode')
    runtime.verify_entity_witnesses(witnesses)
    from src.cluster_statistics import read_witness
    clusters=read_witness(root)
    runtime.check_payload(clusters)
    gates=[]
    if not (root/'CITATION.cff').is_file():gates.append('final author/citation metadata')
    if release_record is None:
        gates.append('manifest-bound technical acceptance and final publication approval record')
    else:
        record=json.loads(Path(release_record).read_text())
        if record.get('manifest_sha256')!=runtime.digest(root/'MANIFEST.sha256'):
            raise ValueError('Release record does not bind the current manifest')
        if record.get('technical_acceptance')!='passed':gates.append('technical acceptance')
        if record.get('publication_approved') is not True or not str(record.get('approved_by','')).strip():
            gates.append('final publication approval')
    if release and gates:raise ValueError('Release gate: '+', '.join(gates))
    return {'mode':'public_statistical_replay','manifest_files':len(files),'movie_record_files':0,
            'movie_near_models':len(witnesses['near']),'release_gates':gates,
            'raw_movie_rescoring':False}


def run_products(root,output,presentation='current'):
    env={**os.environ,'CORE_MODE':'public','CORE_ARTIFACT_ROOT':str(root),
         'CORE_BUILD_DIR':str(output),'CORE_TABLE_DIR':str(output/'tables'),
         'CORE_FIGURE_DIR':str(output/'figures'),'MPLCONFIGDIR':str(output/'.mplconfig'),
         'PYTHONPATH':str(root/'code'),'PYTHONDONTWRITEBYTECODE':'1'}
    for key in ('CORE_PRIVATE_ROOT','CORE_AUTHORIZATION_RECORD','CORE_P2_DIR','CORE_NEAR_DIR','CORE_ALIGNED_DIR'):
        env.pop(key,None)
    output.mkdir(parents=True,exist_ok=False)
    for part in ('derived','tables','figures','.mplconfig'):(output/part).mkdir()
    for name in ('rayyan_audit.json','validate_tables.json'):
        shutil.copyfile(root/'results/derived'/name,output/'derived'/name)
    if presentation=='current':
        env['CORE_COLLECT_ONLY']='1'
        shutil.copytree(root/'results/figures',output/'figures',dirs_exist_ok=True)
    sequence=('rayyan_replay','seeds','scale','paper_tables') if presentation=='current' else ('rayyan_replay','seeds','scale','figures','paper_tables_frozen')
    for name in sequence:
        args=[sys.executable,'-m','src.'+name]
        if name=='rayyan_replay':args+=['--output',str(output/'derived/rayyan_replay.json')]
        subprocess.run(args,cwd=root,env=env,check=True)
    if presentation == 'current':
        from tools.submission_display import apply_current_display
        apply_current_display(root, output)
    return {'mode':'public_statistical_replay','presentation':presentation,'output':str(output)}


def validate_private(root,private,authorization,output):
    private=Path(private).resolve();output=Path(output).resolve()
    if output==private or private in output.parents:
        raise ValueError('Private-validation output must be outside the supplied private source root')
    check=runtime.preflight_private(root,private,authorization)
    sources=json.loads((root/'data/manifests/CORE_SOURCES.json').read_text())
    private=Path(private).resolve()
    for relative,expected in sources['private_code'].items():
        p=private/relative
        if p.is_symlink() or runtime.digest(p)!=expected:raise ValueError('Historical scorer hash mismatch: '+relative)
    if output.exists():raise FileExistsError('Output already exists; no overwrite')
    # Execute only hash-bound original scorers in a temporary overlay. This avoids any
    # dependency fallback or writes to the provided historical source directory.
    with tempfile.TemporaryDirectory(prefix='core-authorized-') as tmp:
        overlay=Path(tmp)/'overlay'
        shutil.copytree(root,overlay,ignore=shutil.ignore_patterns('build','__pycache__','.venv','.git'))
        for relative in set(sources['private_files'])|set(sources['private_code']):
            p=overlay/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(private/relative,p)
        from tools.submission_history import restrict_scoring_modules
        restrict_scoring_modules(overlay, sources['private_code'])
        # Re-score the saved Movie replies using the exact historical source code.
        # P1 remains explicitly a saved-summary projection, not a raw-trial rejudgment.
        import importlib.util
        spec=importlib.util.spec_from_file_location('private_movie_export',root/'tools/export_movie_witnesses.py')
        exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
        rebuilt=exporter.export(overlay);rebuilt['schema_version']=1
        if rebuilt!=runtime.read_witnesses(root):raise ValueError('Private historical scoring differs from public witnesses')
        generated=Path(tmp)/'products'
        env={**os.environ,'CORE_ARTIFACT_ROOT':str(overlay),'CORE_MODE':'public',
             'PYTHON':sys.executable,'PYTHONPATH':str(overlay/'code'),'PYTHONDONTWRITEBYTECODE':'1',
             'CORE_MPLCONFIG_DIR':str(Path(tmp)/'mpl'),'MPLCONFIGDIR':str(Path(tmp)/'mpl')}
        for key in ('CORE_PRIVATE_ROOT','CORE_AUTHORIZATION_RECORD','CORE_P2_DIR','CORE_NEAR_DIR','CORE_ALIGNED_DIR','CORE_BUILD_DIR','CORE_TABLE_DIR','CORE_FIGURE_DIR'):
            env.pop(key,None)
        subprocess.run(['bash',str(overlay/'scripts/reproduce.sh'),'--output',str(generated)],cwd=overlay,env=env,check=True)
        shutil.copytree(generated,output)
    return {**check,'output':str(output),'saved_reply_rescoring':{'p2_archives':84,'near_models':9,'p1':'saved summary only'},
            'raw_historical_scorers_executed':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('verify');p.add_argument('--release',action='store_true');p.add_argument('--release-record',type=Path)
    p=sub.add_parser('reproduce');p.add_argument('--output',type=Path,default=ROOT/'build/reproduced')
    p.add_argument('--presentation',choices=['current','frozen'],default='current')
    p=sub.add_parser('validate-private');p.add_argument('--private-root',type=Path,required=True)
    p.add_argument('--authorization-record',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.environ['CORE_MODE']='public'
    verified=verify(release=getattr(args,'release',False),release_record=getattr(args,'release_record',None))
    if args.command=='verify':result=verified
    elif args.command=='reproduce':result=run_products(ROOT,args.output.resolve(),args.presentation)
    else:result=validate_private(ROOT,args.private_root,args.authorization_record,args.output.resolve())
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
