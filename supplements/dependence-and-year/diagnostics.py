"""Deterministic diagnostics on archived replies; no new intervals, tests or requests."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile

MODELS=['custom_deepseek_deepseek-v4-pro','custom_qwen_qwen3.8-max',
        'custom_z-ai_glm-5.3','openai_gpt-6.1-sol','local_qwen2.5-7b',
        'local_llama3.1-8b','local_qwen2.5-14b','local_qwen2.5-32b-awq']
IDENTITY={'ProviderNumber','HospitalName','Address1','City','ZipCode','CountyName','PhoneNumber'}
KEYS=('errors','predicted','repaired','detected')

def norm(v):return re.sub(r'\s*,\s*',',',' '.join(str(v).lower().split()))

def parse(text):
    left,right=text.find('{'),text.rfind('}')
    if left<0 or right<=left:return []
    try:obj=json.loads(text[left:right+1])
    except json.JSONDecodeError:
        items=[]
        for s in re.findall(r'\{[^{}]*\}',text[left:right+1]):
            try:items.append(json.loads(s))
            except json.JSONDecodeError:pass
        obj={'corrections':items}
    return [p for p in obj.get('corrections',[]) if isinstance(p,dict)
            and {'row','column','value'}<=p.keys()] if isinstance(obj,dict) else []

def effective(dirty,cols,predictions):
    result={}
    for p in predictions:
        try:i=int(p['row'])-1
        except (ValueError,TypeError):continue
        c,v=str(p['column']),str(p['value']).strip()
        if 0<=i<len(dirty) and c in cols and norm(v)!=norm(dirty[i][cols.index(c)]):
            result[i,c]=v
    return result

def f1(c):
    den=c['errors']+c['predicted']
    return 2*c['repaired']/den if den else 0.

def subtract(a,b):
    result={k:v-b.get(k,0) for k,v in a.items()}
    if any(v<0 for v in result.values()):raise ValueError('Negative count after deletion')
    return result

def incidence(replies,unique=False):
    if unique and any(len(x)!=len(set(x)) for x in replies):
        raise ValueError('An entity occurs twice in a main chunk')
    parent={};freq=Counter();sizes=[]
    def find(x):
        parent.setdefault(x,x)
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    for items in replies:
        items=set(items);sizes.append(len(items));freq.update(items)
        if items:
            a=next(iter(items))
            for b in items:parent[find(b)]=find(a)
    components=len({find(x) for x in parent})
    return {'entities':len(parent),'replies':len(replies),'components':components,
            'min_replies_per_entity':min(freq.values(),default=0),
            'max_replies_per_entity':max(freq.values(),default=0),
            'min_entities_per_reply':min(sizes,default=0),
            'max_entities_per_reply':max(sizes,default=0)}

def year_choice(dirty,value):
    years=dirty.split()
    if len(years)!=3:raise ValueError('Expected three candidate years')
    if norm(value)==norm(dirty):return 'unchanged'
    for label,y in zip(('first','middle','last'),years):
        if norm(value)==norm(y):return label
    return 'other'

class Sources:
    def __init__(self,repo,historical_zip):
        self.repo=Path(repo);self.z=zipfile.ZipFile(historical_zip)
        self.private=json.loads((self.repo/'data/manifests/CORE_SOURCES.json').read_text())['private_files']
        self.hashes={'historical_zip':hashlib.sha256(Path(historical_zip).read_bytes()).hexdigest()}
    def read(self,rel):
        p=self.repo/rel
        raw=self.z.read(rel) if rel in self.private else p.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        if rel in self.private:assert digest==self.private[rel],('Historical hash mismatch',rel)
        self.hashes[rel]=digest
        return raw.decode('utf-8')
    def json(self,rel):return json.loads(self.read(rel))
    def table(self,rel):
        rows=list(csv.reader(io.StringIO(self.read(rel))))
        return rows[0],rows[1:]

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def hospital(src,out):
    names=['hospital']+[f'hospital_{v}{suffix}' for suffix in ('','_s1','_s2')
                       for v in ('fresh','surrogatewords','surrogate')]
    _,original=src.table('data/final/hospital/clean.csv')
    headers,_=src.table('data/final/hospital/clean.csv');kj=headers.index('ProviderNumber')
    original_keys=[r[kj] for r in original]
    maps=[];graphs=[];all_counts={};checks=0
    for name in names:
        cols,clean=src.table(f'data/final/{name}/clean.csv')
        _,dirty=src.table(f'data/final/{name}/dirty.csv')
        entities=original_keys if 'surrogate' in name else [r[kj] for r in clean]
        canonical_rows=None
        for model in MODELS:
            rel=f'artifacts/raw_outputs/p2/{model}__{name}__k20__spread.json'
            doc=src.json(rel);by=defaultdict(Counter);total=Counter();replies=[];seen=[]
            for ci,ch in enumerate(doc['chunks']):
                rows=ch['rows'];seen+=rows;ids=[entities[i] for i in rows];replies.append(ids)
                d=[dirty[i] for i in rows];c=[clean[i] for i in rows]
                edits=effective(d,cols,parse(ch['output']));cc=Counter({k:0 for k in KEYS})
                for local,globalrow in enumerate(rows):
                    ec=Counter({k:0 for k in KEYS})
                    for j,col in enumerate(cols):
                        if col not in IDENTITY:continue
                        err=d[local][j]!=c[local][j];ec['errors']+=err
                        if (local,col) in edits:
                            ec['predicted']+=1;ec['detected']+=err
                            ec['repaired']+=bool(err and norm(edits[local,col])==norm(c[local][j]))
                    by[entities[globalrow]].update(ec);cc.update(ec)
                    if model==MODELS[0]:maps.append({'table':name,'row_0based':globalrow,
                        'entity_key':entities[globalrow],'reply_0based':ci})
                assert dict(cc)==ch['counts']['identity'],(rel,ci,cc,ch['counts']['identity'])
                checks+=len(KEYS);total.update(cc)
            assert sorted(seen)==list(range(1000))
            assert all(total[k]==doc['summary']['identity'][k] for k in KEYS)
            assert abs(f1(total)-doc['summary']['identity']['repair_f1'])<=.000051
            indices=[ch['rows'] for ch in doc['chunks']]
            if canonical_rows is None:canonical_rows=indices
            else:assert canonical_rows==indices
            all_counts[model,name]=(total,by)
            if model==MODELS[0]:graphs.append({'table':name,**incidence(replies,unique=True)})
    gaps=[]
    for model in MODELS:
        for seed,suffix in enumerate(('','_s1','_s2')):
            cond={'O':'hospital','F':f'hospital_fresh{suffix}',
                  'W':f'hospital_surrogatewords{suffix}','S':f'hospital_surrogate{suffix}'}
            for a,b in [('O','W'),('W','S'),('O','S'),('F','W'),('O','F')]:
                ta,ea=all_counts[model,cond[a]];tb,eb=all_counts[model,cond[b]]
                full=f1(ta)-f1(tb);vals=[]
                if a!='F' and b!='F':
                    assert set(ea)==set(eb)
                    vals=[f1(subtract(ta,ea[e]))-f1(subtract(tb,eb[e])) for e in ea]
                    scheme='paired entity omitted from both fixed outputs'
                else:
                    vals=[f1(subtract(ta,c))-f1(tb) for c in ea.values()]
                    vals += [f1(ta)-f1(subtract(tb,c)) for c in eb.values()]
                    scheme='one entity omitted on one side; fresh comparison unpaired'
                gaps.append({'model':model,'seed':seed,'contrast':a+'-'+b,'full_difference':full,
                    'deletion_min':min(vals),'deletion_max':max(vals),'deletions':len(vals),
                    'all_positive':all(x>0 for x in vals),'scheme':scheme})
    write_csv(out/'hospital-incidence.csv',maps);write_csv(out/'hospital-graphs.csv',graphs)
    write_csv(out/'hospital-delete-one.csv',gaps)
    return {'runs':len(all_counts),'integer_count_checks':checks,'graphs':graphs,
            'deletion_contrasts':len(gaps),'nonpositive_deletion_ranges':
            [{k:r[k] for k in ('model','seed','contrast','full_difference','deletion_min','deletion_max')}
             for r in gaps if r['full_difference']>0 and not r['all_positive']]}

def conflicts(src,out):
    records=[];graphs=[]
    for ds in ('hospital','beers','movies'):
        plan=src.json(f'data/final/_near/{ds}/plan.json')
        targets={i:p for p in plan['plan'] for i in p['rows']}
        for model in MODELS:
            screen=f'data/final/_near/screen_plan_{ds}__{model}.csv'
            known={r['name'] for r in csv.DictReader(io.StringIO(src.read(screen))) if r['known']=='True'}
            assert known and known<={p['famous']['name'] for p in plan['plan']}
            raw=src.json(f'artifacts/raw_outputs/near/{model}__{ds}.json')
            saved=src.json(f'artifacts/raw_outputs/near/{model}__{ds}__summary.json')
            assert saved['screened_known']['known']==len(known)
            grouped=defaultdict(list)
            for ri,r in enumerate(raw):
                setting='|'.join((r['type'],r['support'],r['prompt']))
                rows=plan['chunk_rows'][r['support']][r['chunk']]
                ids=[]
                for local,row in enumerate(rows):
                    if row not in targets:continue
                    p=targets[row]
                    if p['famous']['name'] not in known:continue
                    ids.append(p['key'])
                    records.append({'dataset':ds,'model':model,'setting':setting,'reply_index':ri,
                        'chunk':r['chunk'],'row_0based':row,'local_row_1based':local+1,'entity_key':p['key']})
                if ids:grouped[setting].append(ids)
            for setting,items in grouped.items():
                g=incidence(items);assert g['entities']==len(known)
                assert saved['key_rates_known'][setting]['entities']==len(known)
                graphs.append({'dataset':ds,'model':model,'setting':setting,'known':len(known),**g})
    write_csv(out/'conflict-incidence.csv',records);write_csv(out/'conflict-graphs.csv',graphs)
    return {'settings':len(graphs),'row_incidence_records':len(records),
            'graphs':graphs,'new_intervals':0,'new_hypothesis_tests':0}

def years(src,out):
    records={};summary=[]
    for cond,name in [('O','movies'),('W','movies_surrogatewords'),('S','movies_surrogate')]:
        cols,clean=src.table(f'data/final/{name}/clean.csv')
        _,dirty=src.table(f'data/final/{name}/dirty.csv');j=cols.index('Year')
        raw=src.json(f'artifacts/raw_outputs/p2/{MODELS[0]}__{name}__k20__spread.json')
        per={}
        for ci,ch in enumerate(raw['chunks']):
            rows=ch['rows'];ds=[dirty[i] for i in rows];ed=effective(ds,cols,parse(ch['output']))
            for local,i in enumerate(rows):
                if dirty[i][j]==clean[i][j]:continue
                value=ed.get((local,'Year'),dirty[i][j]);parts=dirty[i][j].split()
                assert len(parts)==3
                per[i]={'row_0based':i,'dirty_years':dirty[i][j],'reference_year':clean[i][j],
                    'reference_is_middle':norm(clean[i][j])==norm(parts[1]),
                    'choice':year_choice(dirty[i][j],value),'correct':norm(value)==norm(clean[i][j]),
                    'reply_0based':ci,'output_year':value}
        assert len(per)==190
        records[cond]=per
        for middle in (True,False):
            group=[r for r in per.values() if r['reference_is_middle']==middle]
            cnt=Counter(r['choice'] for r in group)
            summary.append({'condition':cond,'reference_group':'middle' if middle else 'not_middle',
                'n':len(group),'correct':sum(r['correct'] for r in group),
                **{k:cnt[k] for k in ('first','middle','last','other','unchanged')}})
    assert all(set(records[c])==set(records['O']) for c in 'WS')
    for i in records['O']:
        assert all((records[c][i]['dirty_years'],records[c][i]['reference_year'])==
                   (records['O'][i]['dirty_years'],records['O'][i]['reference_year']) for c in 'WS')
    assert [sum(r['correct'] for r in records[c].values()) for c in 'OWS']==[173,35,25]
    assert sum(r['reference_is_middle'] for r in records['O'].values())==167
    joint=[]
    for a,b in [('O','W'),('O','S'),('W','S')]:
        cnt=Counter((records[a][i]['choice'],records[b][i]['choice']) for i in records[a])
        joint.extend({'pair':a+'-'+b,'from':x,'to':y,'n':n} for (x,y),n in sorted(cnt.items()))
    # This diagnostic is author-side: it contains row-level historical movie values.
    rows=[{'condition':c,**r} for c,per in records.items() for r in per.values()]
    write_csv(out/'year-private-paired-rows.csv',rows)
    write_csv(out/'year-grouped-counts.csv',summary);write_csv(out/'year-choice-transitions.csv',joint)
    return {'groups':summary,'transitions':joint,'paired_rows':190,
            'not_middle_reference_choices':dict(Counter(year_choice(r['dirty_years'],r['reference_year'])
                for r in records['O'].values() if not r['reference_is_middle']))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,required=True)
    p.add_argument('--historical-zip',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    src=Sources(args.repo_root,args.historical_zip)
    result={'hospital':hospital(src,args.output),'conflicts':conflicts(src,args.output),
            'years':years(src,args.output),'new_model_calls':0,'new_intervals':0,'new_tests':0}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.output/'sources.json').write_text(json.dumps(src.hashes,indent=2)+'\n')
    print(json.dumps({'hospital_runs':result['hospital']['runs'],
        'count_checks':result['hospital']['integer_count_checks'],
        'conflict_settings':result['conflicts']['settings'],'year_groups':result['years']['groups']}))

if __name__=='__main__':main()
