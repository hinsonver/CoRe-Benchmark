"""Export anonymous count/event witnesses from existing replies, without model clients."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,hashlib,importlib.util,io,json,re

def export(root,historical_zip,output):
    root=Path(root);spec=importlib.util.spec_from_file_location('d',root/'supplements/dependence-and-year/diagnostics.py')
    D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)
    src=D.Sources(root,historical_zip);models=D.MODELS;groups=('all','identity','other')
    identity={'hospital':D.IDENTITY,'movies':{'Id','Name','Director','Creator','Actors'},'beers':{'beer-name','brewery-name','city'}}
    keys={'hospital':'ProviderNumber','movies':'Id','beers':'brewery_id'}
    originals={'hospital':'hospital','movies':'movies','beers':'beers_orig'}
    tables={};maps={};conditions={}
    for ds in keys:
        conditions[ds]={'O':originals[ds],'F':ds+'_fresh','W':ds+'_surrogatewords','S':ds+'_surrogate'}
        for c,name in conditions[ds].items():
            cols,clean=src.table(f'data/final/{name}/clean.csv');_,dirty=src.table(f'data/final/{name}/dirty.csv')
            tables[ds,c]=(cols,dirty,clean)
        cols,_,old=tables[ds,'O'];j=cols.index(keys[ds]);oldkeys=[r[j] for r in old]
        fcols,_,fresh=tables[ds,'F'];fj=fcols.index(keys[ds]);freshkeys=[('F:' if ds=='beers' else '')+r[fj] for r in fresh]
        union=sorted(set(oldkeys+freshkeys));lookup={k:i for i,k in enumerate(union)}
        for c in 'OFWS':maps[ds,c]=[lookup[k] for k in (freshkeys if c=='F' else oldkeys)]
        maps[ds,'N']=len(union)
    provenance='supplements/beers-f-input-provenance/'
    bindings={Path(r['run']).name:r for r in src.json(provenance+'run-input-map.json')['runs']}
    checks=Counter()
    def make(ds,c,raw,aligned=False,source=None):
        cols,dirty,clean=tables[ds,c];records=[];totals={g:[0,0,0,0] for g in groups};incomplete=[]
        if not aligned and source and Path(source).name in bindings:
            binding=bindings[Path(source).name]
            assert ds=='beers' and c=='F'
            assert src.hashes[source]==binding['run_sha256']
            cols,dirty=src.table(provenance+binding['scored_input']+'/dirty.csv')
            clean_cols,clean=src.table(provenance+binding['scored_input']+'/clean.csv')
            assert clean_cols==cols
            for kind in ('dirty','clean'):
                assert src.hashes[provenance+binding['scored_input']+'/'+kind+'.csv']==binding['input_sha256'][kind]
            checks['historical_input_runs']+=1
        chunks=raw if aligned else raw['chunks']
        for bi,ch in enumerate(chunks):
            rows=ch['rows'];part={g:[0,0,0,0] for g in groups}
            if aligned:
                edits={(int(i),str(col)):str(v) for i,col,v in ch['fixes']}
            else:
                d=[dirty[i] for i in rows];ed=D.effective(d,cols,D.parse(ch.get('output','')))
                edits={(rows[local],col):v for (local,col),v in ed.items()}
                if ch.get('output','').strip()=='{"':incomplete.append(bi)
            block=[]
            for i in rows:
                counts={g:[0,0,0,0] for g in groups}
                for j,col in enumerate(cols):
                    err=dirty[i][j]!=clean[i][j];v=edits.get((i,col))
                    proposed=v is not None and D.norm(v)!=D.norm(dirty[i][j])
                    if aligned:proposed=bool(err and proposed)
                    repaired=bool(err and proposed and D.norm(v)==D.norm(clean[i][j]))
                    inc=[int(err),int(proposed),int(repaired),int(err and proposed)]
                    for g in ('all','identity' if col in identity[ds] else 'other'):
                        counts[g]=[a+b for a,b in zip(counts[g],inc)]
                block.append([i,maps[ds,c][i],bi]+sum((counts[g] for g in groups),[]))
                for g in groups:part[g]=[a+b for a,b in zip(part[g],counts[g])]
            if not aligned:
                expected={g:[ch['counts'][g][k] for k in D.KEYS] for g in groups}
                if part!=expected:
                    raise ValueError(('Count mismatch',source,ds,c,bi,part,expected))
                for g in groups:totals[g]=[a+b for a,b in zip(totals[g],expected[g])]
                checks['archived_integer_bindings']+=12
                if part==expected:checks['integer_count_checks']+=12
            else:
                for g in groups:totals[g]=[a+b for a,b in zip(totals[g],part[g])]
            records+=block
        if not aligned:
            for g in groups:assert totals[g]==[raw['summary'][g][k] for k in D.KEYS]
        checks['archives']+=1
        return {'rows':records,'totals':totals,'entities':maps[ds,'N'],
                'replies':len(chunks),'incomplete':incomplete,'descriptive':ds=='beers' and c=='F' and not aligned,
                'row_allocation_available':True}
    out={'schema':1,'models':models,'group_order':groups,'main':{},'aligned':{},'near':{},'source_sha256':{}}
    for model in models:
        out['main'][model]={}
        for ds,conds in conditions.items():
            out['main'][model][ds]={c:make(ds,c,src.json(f'artifacts/raw_outputs/p2/{model}__{name}__k20__spread.json'),source=f'artifacts/raw_outputs/p2/{model}__{name}__k20__spread.json')
                                     for c,name in conds.items()}
        print('counts',model,flush=True)
    for ds,conds in conditions.items():
        out['aligned'][ds]={'llm':{},'baran':{}}
        for c,name in conds.items():
            out['aligned'][ds]['llm'][c]=make(ds,c,src.json(f'artifacts/raw_outputs/aligned/{models[0]}__{name}.json'),True)
            out['aligned'][ds]['baran'][c]=[make(ds,c,src.json(f'artifacts/raw_outputs/aligned/baran__{name}__run{k}.json'),True) for k in range(3)]
    keycols={('hospital','real'):'City',('hospital','near'):'HospitalName',('beers','real'):'city',('beers','near'):'brewery-name',('movies','real'):'Director',('movies','near'):'Name'}
    def place(v):return re.sub(r'[^a-z ]','',D.norm(v).replace('saint ','st ').replace('st. ','st ').replace('mount ','mt ')).strip()
    def isfact(ds,col,v,t):
        if col==keycols[ds,'near']:return D.norm(v)==D.norm(t['name'])
        if ds=='movies':return any(x and D.norm(x) in D.norm(v) for x in t['director'].split(','))
        return place(v)==place(t['city'])
    for model in models:
        out['near'][model]={}
        for ds in ('hospital','beers','movies'):
            plan=src.json(f'data/final/_near/{ds}/plan.json')
            known={r['name'] for r in csv.DictReader(io.StringIO(src.read(f'data/final/_near/screen_plan_{ds}__{model}.csv'))) if r['known']=='True'}
            targets={i:(ei,p) for ei,p in enumerate(plan['plan']) for i in p['rows'] if p['famous']['name'] in known}
            clean={t:src.table(f'data/final/_near/{ds}/{t}/clean.csv') for t in ('real','near','control')}
            per=defaultdict(dict)
            for ch in src.json(f'artifacts/raw_outputs/near/{model}__{ds}.json'):
                setting='|'.join((ch['type'],ch['support'],ch['prompt']));col=keycols[ds,'real' if ch['type']=='control' else ch['type']]
                cols,table=clean[ch['type']];j=cols.index(col);edits={}
                for p in D.parse(ch['output']):
                    try:edits[int(p['row'])-1,str(p['column'])]=str(p['value'])
                    except (ValueError,TypeError):continue
                for local,i in enumerate(plan['chunk_rows'][ch['support']][ch['chunk']]):
                    if i not in targets:continue
                    ei,p=targets[i];v=edits.get((local,col))
                    hit=bool(v is not None and D.norm(v)!=D.norm(table[i][j]) and isfact(ds,col,v,p['famous']))
                    if ei not in per[setting]:per[setting][ei]={'entity':ei,'reply':ch['chunk'],'hits':[]}
                    assert per[setting][ei]['reply']==ch['chunk'];per[setting][ei]['hits'].append(hit)
            out['near'][model][ds]={k:list(v.values()) for k,v in per.items()}
            saved=src.json(f'artifacts/raw_outputs/near/{model}__{ds}__summary.json')['key_rates_known']
            for setting,events in out['near'][model][ds].items():
                means=[sum(e['hits'])/len(e['hits']) for e in events]
                assert len(events)==len(known)==saved[setting]['entities']
                assert round(sum(means)/len(means),3)==saved[setting]['rate']
                checks['near_settings']+=1
    out['source_sha256']=src.hashes;out['verification']=dict(checks)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(out,separators=(',',':'))+'\n')
    binding={'schema':1,'file':str(output.relative_to(root)),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
             'row_schema':['row_index','entity_index','reply_index','E_all','P_all','R_all','D_all','E_identity','P_identity','R_identity','D_identity','E_other','P_other','R_other','D_other'],
             'sources':src.hashes,'verification':dict(out['verification'])}
    (root/'data/manifests/CLUSTER_STATISTICS.json').write_text(json.dumps(binding,indent=2)+'\n')
    print(json.dumps(binding['verification']))
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--historical-zip',type=Path,required=True);ap.add_argument('--output',type=Path)
    a=ap.parse_args();root=Path(__file__).resolve().parents[1]
    export(root,a.historical_zip,a.output or root/'data/witnesses/cluster_statistics.json')
