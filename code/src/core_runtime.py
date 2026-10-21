"""Explicit, hash-bound statistical evidence; no movie records in public mode."""
import copy
import collections
import fnmatch
from functools import lru_cache
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import random


def root_path():
    return Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_mode():
    mode=os.environ.get('CORE_MODE','public')
    if mode not in ('public','authorized'):
        raise ValueError('CORE_MODE must be public or authorized')
    return mode=='public'


def check_payload(value):
    forbidden={'output','fixes','examples','famous','tconst','nconst','answer','truth','pred','real_orig'}
    if isinstance(value,dict):
        for k,v in value.items():
            if k in forbidden:raise ValueError('Forbidden movie record payload field: '+k)
            check_payload(v)
    elif isinstance(value,list):
        for v in value:check_payload(v)
    elif isinstance(value,str) and re.search(r'\b(?:tt|nm)\d{7,}\b',value):
        raise ValueError('Forbidden movie identifier payload')


@lru_cache(maxsize=2)
def _parse_witness(data):
    # Callers treat this shared parsed representation as read-only; public views
    # and archive reads return deep copies. Every read still hashes current bytes.
    value=json.loads(data)
    if value.get('schema_version')!=1:raise ValueError('Unsupported witness schema')
    check_payload(value)
    return value


def read_witnesses(root=None):
    root=Path(root or root_path())
    binding=json.loads((root/'data/manifests/CORE_WITNESSES.json').read_text())
    relative='data/witnesses/movies.json'
    expected=binding['files'].get(relative)
    if not expected:raise ValueError('Missing movie witness hash binding')
    path=root/relative
    if path.is_symlink():raise ValueError('Witness symlink forbidden')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Movie witness hash mismatch')
    return _parse_witness(data)


def movie_view(name,root=None):
    value=read_witnesses(root)['views']
    if name not in value:raise ValueError('Missing numerical movie view: '+name)
    return copy.deepcopy(value[name])


def rates_from_events(events,only_known=False,n_boot=2000):
    """Recompute the frozen entity bootstrap from anonymous flags (seed 0)."""
    groups=collections.defaultdict(dict)
    for event in events:
        if only_known and not event['known']:continue
        group=groups[event['setting']]
        if event['entity'] in group:raise ValueError('Duplicate entity/setting witness')
        if not event['key_hits']:raise ValueError('Empty entity witness')
        group[event['entity']]=event['key_hits']
    out={}
    for setting,entities in sorted(groups.items()):
        means=[sum(hits)/len(hits) for hits in entities.values()]
        rng=random.Random(0)
        boot=sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(n_boot))
        out[setting]={'rate':round(sum(means)/len(means),3),
                      'ci':[round(boot[int(.025*n_boot)],3),round(boot[int(.975*n_boot)-1],3)],
                      'entities':len(means)}
    return out


def verify_entity_witnesses(witnesses):
    for model,record in witnesses['near'].items():
        for known,key in ((False,'key_rates'),(True,'key_rates_known')):
            if rates_from_events(record['events'],known)!=record['summary'][key]:
                raise ValueError('Entity bootstrap differs from frozen result: '+model+'/'+key)
    return len(witnesses['near'])


def relative_to_root(path,root):
    p=Path(path)
    if not p.is_absolute():p=root/p
    try:return p.relative_to(root).as_posix()
    except ValueError:raise ValueError('Evidence path is outside package')


def is_movie_path(relative):
    return 'movies' in relative and relative.startswith(('data/final/','artifacts/raw_outputs/'))


def preflight_private(root,private_root,authorization):
    root=Path(root).resolve()
    if authorization is None:raise ValueError('An authorization record is required; no permission is inferred')
    auth_path=Path(authorization)
    if not auth_path.is_file() or auth_path.is_symlink():raise ValueError('Invalid authorization record')
    auth=json.loads(auth_path.read_text())
    if not all(isinstance(auth.get(k),str) and auth[k].strip() for k in ('purpose','rights_basis')):
        raise ValueError('authorization must identify purpose and rights_basis')
    if not {'historical_inputs','historical_outputs'}<=set(auth.get('scope',[])) or auth.get('redistribution') is not False:
        raise ValueError('authorization scope must cover historical inputs/outputs, without redistribution')
    private=Path(private_root).resolve()
    if private==root or root in private.parents:
        raise ValueError('Private root must be external to the public package')
    files=json.loads((root/'data/manifests/CORE_SOURCES.json').read_text())['private_files']
    if not files:raise ValueError('Empty private dependency manifest')
    for relative,expected in files.items():
        rel=Path(relative)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe private dependency path')
        p=private/rel
        if not p.is_file():raise FileNotFoundError('Required private dependency missing: '+relative)
        if any(q.is_symlink() for q in [p,*p.parents] if q!=private.parent):
            raise ValueError('Private dependency symlink forbidden: '+relative)
        if digest(p)!=expected:raise ValueError('Private dependency hash mismatch: '+relative)
    return {'mode':'authorized','private_files_verified':len(files),
            'authorization_record_sha256':digest(auth_path),
            'rights_basis_recorded_not_legally_adjudicated':True,'redistribution_authorized':False}


def private_file(relative,root=None):
    root=Path(root or root_path())
    if public_mode():raise ValueError('Movie row values are excluded from public statistical replay')
    private=os.environ.get('CORE_PRIVATE_ROOT');auth=os.environ.get('CORE_AUTHORIZATION_RECORD')
    if not private:raise ValueError('Explicit private root required')
    preflight_private(root,private,auth)
    return Path(private)/relative


def evidence_json(path,root=None):
    root=Path(root or root_path());relative=relative_to_root(path,root)
    if is_movie_path(relative):
        if not public_mode():return json.loads(private_file(relative,root).read_text())
        archives=read_witnesses(root)['archives']
        if relative not in archives:
            raise FileNotFoundError('No bound public statistical witness: '+relative)
        return copy.deepcopy(archives[relative])
    from . import scope_runtime as scoped
    if scoped.is_controlled(relative,root):
        if not public_mode():return json.loads(private_file(relative,root).read_text())
        return scoped.archive(relative,root)
    return json.loads((root/relative).read_text())


def evidence_glob(pattern,root=None):
    root=Path(root or root_path());relative=relative_to_root(pattern,root)
    found=set(glob.glob(str(root/relative)))
    if public_mode():
        from .scope_runtime import read_scope
        for name in set(read_witnesses(root)['archives'])|set(read_scope(root)['archives']):
            if fnmatch.fnmatchcase(name,relative):found.add(str(root/name))
    else:
        for name in json.loads((root/'data/manifests/CORE_SOURCES.json').read_text())['private_files']:
            if fnmatch.fnmatchcase(name,relative):found.add(str(root/name))
    return sorted(found)


def evidence_paths(folder,pattern,root=None):
    return [Path(p) for p in evidence_glob(Path(folder)/pattern,root)]


def movie_known_key_rates(model,summary,root=None):
    tag=model.replace(':','_').replace('/','_')
    witnesses=read_witnesses(root)
    if tag not in witnesses['near']:raise FileNotFoundError('Movie known-entity witness missing: '+tag)
    record=witnesses['near'][tag];expected=record['summary']
    if summary.get('screened_known')!=expected['screened_known']:
        raise ValueError('Movie known-entity denominator mismatch')
    if summary.get('key_rates_known')!=expected['key_rates_known']:
        raise ValueError('Movie known-entity rate/interval mismatch')
    if not expected['screened_known']['known']:raise ValueError('Empty known subset; no fallback permitted')
    return copy.deepcopy(expected['key_rates_known'])
