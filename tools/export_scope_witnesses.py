"""Export A04 numerical projections from explicitly supplied, hash-bound originals.

This module never calls a model. It uses the companion's original scoring code;
P1 and older P2 archives without saved block-row mappings are identified
as saved-summary/count projections rather than newly rescored observations.
"""
import collections
import ast
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path


def numeric(value):
    if isinstance(value,dict):
        return {k:numeric(v) for k,v in value.items()
                if k not in {'output','fixes','examples','answer','truth','pred','famous','real_orig'}
                and (isinstance(v,(dict,list,int,float,bool)) or v is None)}
    if isinstance(value,list):
        return [numeric(v) for v in value if isinstance(v,(dict,list,int,float,bool)) or v is None]
    return value


def project_p2(value):
    chunks=[]
    for ch in value['chunks']:
        reply=ch.get('output','').strip()
        chunks.append({'start':int(ch['start']),'counts':numeric(ch['counts']),
                       'truncated':not reply or not reply.endswith(('}','```'))})
        if 'rows' in ch:chunks[-1]['rows']=[int(i) for i in ch['rows']]
    return {'summary':value['summary'],'chunks':chunks}


def original_exporter(root):
    spec=importlib.util.spec_from_file_location('_a04_movie_export',Path(root)/'tools/export_movie_witnesses.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def near_record(ds,model,source,modules,movie):
    ne,pc=modules['near_entities'],modules['probe_clean']
    read=lambda p:json.loads(p.read_text())
    plan=read(source/f'data/final/_near/{ds}/plan.json')
    summary=numeric(read(source/f'artifacts/raw_outputs/near/{model}__{ds}__summary.json'))
    known=ne.known_names(ds,model)
    modules['screening'].known_key_rates(source/'data/final/_near',ds,model,summary)
    tables={t:modules['data'].load(f'_near/{ds}/{t}')[1] for t in ne.TYPES}
    targets={i:(ordinal,p) for ordinal,p in enumerate(plan['plan']) for i in p['rows']}
    groups=collections.OrderedDict()
    for record in read(source/f'artifacts/raw_outputs/near/{model}__{ds}.json'):
        rows=plan['chunk_rows'][record['support']][record['chunk']]
        setting='|'.join((record['type'],record['support'],record['prompt']))
        col=ne.KEY_COLUMN[(ds,'real' if record['type']=='control' else record['type'])]
        edits={}
        for pred in pc.parse(record['output']):
            try:edits[(int(pred['row'])-1,str(pred['column']))]=str(pred['value'])
            except (TypeError,ValueError):continue
        clean=tables[record['type']]
        for j,i in enumerate(rows):
            if i not in targets:continue
            ordinal,target=targets[i]
            event=groups.setdefault((setting,ordinal),{'setting':setting,'entity':ordinal,
                'known':target['famous']['name'] in known,'key_hits':[],'cells':[]})
            v=edits.get((j,col));changed=v is not None and pc.norm(v)!=pc.norm(clean.at[i,col])
            event['key_hits'].append(bool(changed and ne._is_fact(ds,col,v,target['famous'])))
            for c in ne.WATCH[ds]:
                v=edits.get((j,c));changed=v is not None and pc.norm(v)!=pc.norm(clean.at[i,c])
                event['cells'].append({'column':c,'changed':bool(changed),
                    'to_fact':bool(changed and ne._is_fact(ds,c,v,target['famous']))})
    events=list(groups.values())
    for known_only,key in [(False,'key_rates'),(True,'key_rates_known')]:
        derived=movie.rates_from_events(events,known_only)
        if derived!=ne.key_rates(ds,model,only_known=known_only) or derived!=summary[key]:
            raise ValueError('C2 original scoring/flags/interval mismatch: '+ds+'/'+model+'/'+key)
    return {'summary':summary,'events':events}


def export(source,metadata_root=None):
    source=Path(source).resolve();metadata_root=Path(metadata_root or source)
    binding=json.loads((metadata_root/'data/manifests/SCOPE_SOURCES.json').read_text())
    hashes={**binding['controlled_files'],**binding['export_dependencies']}
    for name,expected in hashes.items():
        p=source/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('A04 source hash mismatch: '+name)
    movie=original_exporter(metadata_root)
    archives,near,coverage,views={},{},{},{}
    with movie._original_modules(source) as modules:
        pc=modules['probe_clean'];frames={}
        for name in sorted(binding['controlled_files']):
            p=source/name
            if not p.suffix=='.json' or '/e4/' in name:continue
            value=json.loads(p.read_text());family=p.parent.name
            if family=='p2':
                projected=project_p2(value);ds=value['summary']['dataset']
                if ds not in frames:frames[ds]=modules['data'].load(ds)
                dirty,clean=frames[ds];disagreements=[];missing_rows=[]
                for ordinal,ch in enumerate(value['chunks']):
                    if 'rows' not in ch:
                        missing_rows.append(ordinal);continue
                    rows=ch['rows']
                    actual=pc.score_chunk(dirty.iloc[rows].reset_index(drop=True),
                        clean.iloc[rows].reset_index(drop=True),pc.parse(ch['output']),pc.IDENTITY[ds.split('_')[0]])
                    if actual!=ch['counts']:disagreements.append(ordinal)
                for group in ['all','identity','other']:
                    if pc.metrics(pc.total(projected['chunks'],group))!=value['summary'][group]:
                        raise ValueError('P2 saved counts/summary disagree: '+name+'/'+group)
                coverage[name]={'blocks':len(value['chunks']),'raw_rejudged_blocks':len(value['chunks'])-len(disagreements)-len(missing_rows),
                    'input_version_mismatch_blocks':disagreements,
                    'row_mapping_unavailable_blocks':missing_rows,
                    'public_object':'archived block counts; pairing and interval inputs retained'}
            elif family=='p1':
                projected={'summary':numeric(value['summary'])}
                coverage[name]={'public_object':'saved historical summary; raw trial rejudgment not claimed'}
            elif family=='aligned' and isinstance(value,list):
                ds=p.stem.split('__')[1]
                projected={'__core_witness__':'aligned_counts_v1','chunks':modules['aligned'].score(ds,value)}
                coverage[name]={'public_object':'original aligned scorer counts','chunks':len(projected['chunks'])}
            elif family=='near' and not p.stem.endswith('__summary'):continue
            else:projected=numeric(value)
            archives[name]=projected
        for name in sorted(binding['controlled_files']):
            p=Path(name)
            if p.parent.name!='near' or not p.stem.endswith('__summary'):continue
            model,ds,_=p.stem.split('__')
            rec=near_record(ds,model,source,modules,movie);near[ds+'|'+model]=rec
            archives[f'artifacts/raw_outputs/near/{model}__{ds}.json']={
                '__core_witness__':'near_events_v1','events':rec['events']}
            archives[name]=rec['summary']
        rr=importlib.import_module(modules['probe_clean'].__package__+'.rayyan_replay')
        scale=importlib.import_module(modules['probe_clean'].__package__+'.scale')
        views['beers_city']={tag:scale.beers_city(tag) for tag,_,_ in scale.MODELS if tag.startswith('custom_')}
        tables=importlib.import_module(modules['probe_clean'].__package__+'.paper_tables')
        tree=ast.parse((source/'code/src/paper_tables.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='decoding_table')
        cut=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='rows' for t in n.targets))
        # Keep the exact original classification/repaired functions; expose their
        # numerical counters before the table-rendering portion, without values.
        fn.body=fn.body[:cut]+[ast.parse("return {'population':dict(n),'repaired':{tag:dict(repaired(tag)) for tag,_ in COMMERCIAL if tag.startswith('custom_')}}").body[0]]
        code=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
        namespace=dict(vars(tables));exec(compile(code,'original-decoding-numerical-view','exec'),namespace)
        views['hospital_decoding']=namespace['decoding_table']()
        raw_result=rr.replay(source)
        cols,dirty=rr.read_csv(source/'artifacts/raw_outputs/e4/inputs/rayyan/dirty.csv')
        _,clean=rr.read_csv(source/'artifacts/raw_outputs/e4/inputs/rayyan/clean.csv',cols)
        _,out=rr.read_csv(source/'artifacts/raw_outputs/e4/tabclean/rayyan/final_cleaned.csv',cols)
        ns=rr.functions(source);cells=[]
        for i,(d,g,v) in enumerate(zip(dirty,clean,out)):
            for c in cols:
                err=d[c]!=g[c];changed=ns['norm'](v[c])!=ns['norm'](d[c])
                repaired=changed and err and ns['norm'](v[c])==ns['norm'](g[c])
                if err or changed:
                    cells.append({'row':i,'column':c,'error':bool(err),'changed':bool(changed),
                        'repaired':bool(repaired),'date_conversion':bool(repaired and c=='article_jcreated_at'
                                                                 and v[c]==rr.date_conversion(d[c]))})
        indices=json.loads((source/'data/provenance/rayyan/dev-row-indices.json').read_text())['indices_0based_in_sample_order']
        rayyan={'cells':cells,'dev_indices':indices,'full_input_errors':960,'scored_rows':850,
                'raw_verification':{'counts':raw_result['tabclean'],'date_conversions':raw_result['credited_date_conversions']}}
    return {'schema_version':1,'archives':archives,'near':near,'rayyan':rayyan,'views':views,
            'source_sha256':hashes,'coverage':coverage}
