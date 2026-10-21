"""Hash-bound A04 numerical evidence; withheld originals are never implicit inputs."""
import collections
import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import re


def root_path():
    return Path(__file__).resolve().parents[2]


def check_numeric_payload(value):
    forbidden={'output','answer','examples','fixes','truth','pred','famous','real_orig','dirty','clean'}
    if isinstance(value,dict):
        for k,v in value.items():
            if k in forbidden:raise ValueError('Withheld record payload field: '+k)
            check_numeric_payload(v)
    elif isinstance(value,list):
        for x in value:check_numeric_payload(x)
    elif isinstance(value,str) and re.search(r'\b(?:tt|nm)\d{7,}\b',value):
        raise ValueError('Movie identifier in numerical witness')


@lru_cache(maxsize=2)
def parse(data):
    value=json.loads(data)
    if value.get('schema_version')!=1:raise ValueError('Unsupported A04 witness schema')
    check_numeric_payload(value)
    return value


def read_scope(root=None):
    root=Path(root or root_path())
    relative='data/witnesses/scoped.json'
    p=root/relative
    binding=json.loads((root/'data/manifests/SCOPE_WITNESSES.json').read_text())
    expected=binding.get('files',{}).get(relative)
    if not expected or p.is_symlink():raise ValueError('Missing/unsafe A04 witness hash binding')
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('A04 witness hash mismatch')
    return parse(data)


def source_manifest(root=None):
    root=Path(root or root_path())
    return json.loads((root/'data/manifests/SCOPE_SOURCES.json').read_text())


def is_controlled(relative,root=None):
    return relative in source_manifest(root)['controlled_files']


def archive(relative,root=None):
    value=read_scope(root)['archives']
    if relative not in value:raise FileNotFoundError('No A04 numerical witness for withheld evidence: '+relative)
    return copy.deepcopy(value[relative])


def view(name,root=None):
    values=read_scope(root)['views']
    if name not in values:raise FileNotFoundError('Missing A04 numerical view: '+name)
    return copy.deepcopy(values[name])


def metrics(c):
    f=lambda a,b:2*a*b/(a+b) if a+b else 0.0
    p=c['repaired']/c['predicted'] if c['predicted'] else 0.0
    r=c['repaired']/c['errors'] if c['errors'] else 0.0
    dp=c['detected']/c['predicted'] if c['predicted'] else 0.0
    dr=c['detected']/c['errors'] if c['errors'] else 0.0
    return {'repair_p':round(p,4),'repair_r':round(r,4),'repair_f1':round(f(p,r),4),
            'detect_f1':round(f(dp,dr),4),**dict(c)}


def rates(events,only_known=False):
    groups=collections.defaultdict(dict)
    for e in events:
        if type(e['known']) is not bool or not isinstance(e['entity'],int):raise ValueError('Invalid anonymous entity')
        if only_known and not e['known']:continue
        if e['entity'] in groups[e['setting']]:raise ValueError('Duplicate anonymous entity/setting')
        hits=e['key_hits']
        if not hits or any(type(x) is not bool for x in hits):raise ValueError('Invalid entity hit flags')
        groups[e['setting']][e['entity']]=hits
    out={}
    for setting,entities in sorted(groups.items()):
        means=[sum(v)/len(v) for v in entities.values()]
        rng=random.Random(0)
        boot=sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(2000))
        out[setting]={'rate':round(sum(means)/len(means),3),
                      'ci':[round(boot[50],3),round(boot[1949],3)],'entities':len(means)}
    return out


def known_rates_from_record(record):
    s=record['summary'];events=record['events']
    pool={e['entity'] for e in events}
    known={e['entity'] for e in events if e['known']}
    flags={}
    for e in events:
        if e['entity'] in flags and flags[e['entity']]!=e['known']:raise ValueError('Known flag changes by setting')
        flags[e['entity']]=e['known']
    if not known or s.get('screened_known')!={'known':len(known),'targets':len(pool)}:
        raise ValueError('Known-subset denominator mismatch; no fallback')
    all_rates=rates(events)
    known_rates=rates(events,True)
    if all_rates!=s.get('key_rates') or known_rates!=s.get('key_rates_known'):
        raise ValueError('Entity flags/rates/intervals mismatch')
    return known_rates


def known_key_rates(ds,model,summary,root=None):
    key=ds+'|'+model.replace(':','_').replace('/','_')
    record=read_scope(root)['near'].get(key)
    if record is None:raise FileNotFoundError('Missing anonymous screening witness: '+key)
    rates_=known_rates_from_record(record)
    if summary.get('screened_known')!=record['summary']['screened_known'] or summary.get('key_rates_known')!=rates_:
        raise ValueError('Summary disagrees with fixed screening witnesses')
    return copy.deepcopy(rates_)


def rayyan_counts(flags,skip,metric=metrics):
    totals={g:collections.Counter(errors=0,predicted=0,detected=0,repaired=0) for g in ['all','identity','other']}
    identity={'article_title','journal_title','author_list'}
    columns={'id','article_title','article_language','journal_title','jounral_abbreviation','journal_issn',
             'article_jvolumn','article_jissue','article_jcreated_at','article_pagination','author_list'}
    seen=set();dates=[]
    for e in flags:
        key=(e['row'],e['column'])
        if key in seen or not 0<=e['row']<1000 or e['column'] not in columns:raise ValueError('Invalid/duplicate cell witness')
        seen.add(key)
        for k in ['error','changed','repaired','date_conversion']:
            if type(e[k]) is not bool:raise ValueError('Nonboolean cell outcome')
        if e['repaired'] and not(e['error'] and e['changed']):raise ValueError('Impossible credited repair')
        if e['date_conversion'] and not(e['repaired'] and e['column']=='article_jcreated_at'):
            raise ValueError('Impossible date-conversion credit')
        if e['row'] in skip:continue
        c={'errors':int(e['error']),'predicted':int(e['changed']),
           'detected':int(e['error'] and e['changed']),'repaired':int(e['repaired'])}
        for group in ['all','identity' if e['column'] in identity else 'other']:totals[group].update(c)
        if e['date_conversion']:dates.append(e['row'])
    return {g:metric(c) for g,c in totals.items()},dates


def verify_scope(root=None):
    root=Path(root or root_path());manifest=source_manifest(root);w=read_scope(root)
    files=manifest['controlled_files']
    if len(files)!=138 or any((root/p).exists() for p in files):raise ValueError('Withheld originals present/missing disposition')
    if w['source_sha256']!={**files,**manifest['export_dependencies']}:
        raise ValueError('Numerical witness/source binding differs')
    overlaps=manifest['public_identical_bytes']
    for name,item in overlaps.items():
        path=item['public_path']
        if name not in files or path in files or item['sha256']!=files[name] or hashlib.sha256((root/path).read_bytes()).hexdigest()!=files[name]:
            raise ValueError('Independently public identical-byte provenance mismatch')
    for record in w['near'].values():known_rates_from_record(record)
    r=w['rayyan'];skip=set(r['dev_indices'])
    if len(skip)!=150 or len(skip)!=len(r['dev_indices']):raise ValueError('Rayyan development denominator')
    totals,dates=rayyan_counts(r['cells'],skip)
    if [totals['all'][k] for k in ['errors','predicted','detected','repaired']]!=[808,498,497,461] or len(dates)!=434:
        raise ValueError('Rayyan anonymous counts differ from frozen result')
    if sum(e['error'] for e in r['cells'])!=960:raise ValueError('Wrong TabClean input version witness')
    return {'controlled_original_paths_absent':len(files),'numerical_archives':len(w['archives']),
            'anonymous_conflict_models':len(w['near']),'rayyan_cell_outcomes':len(r['cells']),
            'raw_withheld_rejudgment':False,'independently_public_identical_byte_paths':len(overlaps)}
