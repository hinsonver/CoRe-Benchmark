"""Conditional entity/reply inference from anonymous integer and event witnesses."""
from collections import defaultdict
from pathlib import Path
import hashlib,json
import numpy as np

GROUPS=('all','identity','other')
SEED=20261027
B=50000

def condition_code(label):
    labels={'Original':'O','Fresh':'F','Words':'W','Syllable':'S','Words surrogate':'W','Syllable surrogate':'S',**{k:k for k in 'OFWS'}}
    if label not in labels:raise ValueError('Unknown condition label: '+label)
    return labels[label]

def weighted_f1(counts,weights):
    counts=np.asarray(counts,float);weights=np.asarray(weights,float)
    if np.any(weights<0):raise ValueError('Negative weight')
    t=weights@counts;d=t[:,0]+t[:,1]
    return np.divide(2*t[:,2],d,out=np.zeros(len(d)),where=d!=0)

def cluster_rates(nums,dens,weights):
    den=np.asarray(weights)@np.asarray(dens)
    if np.any(den<=0):raise ValueError('Empty entity denominator')
    return (np.asarray(weights)@np.asarray(nums))/den

def centered_p(values,point):
    if point==0:return 1.
    return (1+int(np.count_nonzero(np.abs(values-point)>=abs(point))))/(len(values)+1)

def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]);result=[0.]*len(ps);running=0.
    for rank,i in enumerate(order):
        running=max(running,min(1.,(len(ps)-rank)*float(ps[i])));result[i]=running
    return result

def percentile(values):return [float(v) for v in np.quantile(values,[.025,.975],method='linear')]

def interval_record(values,point):
    if values is None:return {'point':float(point),'ci':None,'interval_available':False,'kind':'descriptive'}
    ci=percentile(values);available=ci[0]!=ci[1]
    return {'point':float(point),'ci':ci,'interval_available':available,
            'kind':'cluster_percentile' if available else 'empirical_constant'}

def matrix(entry,group):
    rows=np.asarray(entry['rows'],float);j=3+4*GROUPS.index(group)
    return rows[:,j:j+3]

def score(entry,group):
    e,p,r,_=entry['totals'][group]
    return 2*r/(e+p) if e+p else 0.

def series(entry,group,ew,rw):
    rows=np.asarray(entry['rows']);ei=rows[:,1].astype(int);bi=rows[:,2].astype(int)
    counts=matrix(entry,group);parts=[]
    for start in range(0,len(rw),1000):
        w=rw[start:start+1000,bi]
        if ew is not None:w=w*ew[start:start+1000,ei]
        parts.append(weighted_f1(counts,w))
    return np.concatenate(parts)

def draw_series(entries,dataset,group,n=B,seed=SEED):
    rng=np.random.default_rng(seed)
    active=[v for v in entries.values() if not v.get('descriptive',False)]
    ne=max(v['entities'] for v in entries.values())
    ew=None if dataset=='movies' else rng.exponential(1.,size=(n,ne))
    rw=rng.exponential(1.,size=(n,entries['O']['replies']))
    frw=rng.exponential(1.,size=(n,entries['F']['replies']))
    return {c:None if e.get('descriptive',False) else series(e,group,ew,frw if c=='F' else rw)
            for c,e in entries.items()}

def rate_interval(events,n=B,seed=SEED):
    grouped=defaultdict(list);seen=set();means=[]
    for e in events:
        if e['entity'] in seen or not e['hits']:raise ValueError('Duplicate or empty entity')
        seen.add(e['entity']);m=sum(e['hits'])/len(e['hits']);means.append(m)
        grouped[e['reply']].append(m)
    keys=sorted(grouped);num=[sum(grouped[k]) for k in keys];den=[len(grouped[k]) for k in keys]
    weights=np.random.default_rng(seed).multinomial(len(keys),np.full(len(keys),1/len(keys)),size=n)
    values=cluster_rates(num,den,weights);rate=sum(means)/len(means)
    rec=interval_record(values,rate)
    return {'rate':round(rate,3),'rate_exact':rate,'ci':rec['ci'],'interval_available':rec['interval_available'],
            'kind':rec['kind'],'entities':len(means),'replies':len(keys),'rewritten':sum(means)}

def read_witness(root):
    root=Path(root);p=root/'data/witnesses/cluster_statistics.json'
    binding=json.loads((root/'data/manifests/CLUSTER_STATISTICS.json').read_text())
    if hashlib.sha256(p.read_bytes()).hexdigest()!=binding['sha256']:raise ValueError('Cluster witness hash mismatch')
    d=json.loads(p.read_text())
    if d['schema']!=1:raise ValueError('Cluster witness schema')
    return d

def subset(entry,keep):
    out={**entry};ids=sorted(keep);mapping={v:i for i,v in enumerate(ids)}
    out['rows']=[r[:2]+[mapping[r[2]]]+r[3:] for r in entry['rows'] if r[2] in keep]
    out['replies']=len(ids)
    out['totals']={g:np.asarray(out['rows'])[:,3+4*j:7+4*j].sum(axis=0).astype(int).tolist() for j,g in enumerate(GROUPS)}
    return out

def run(root,output,n=B,seed=SEED):
    root=Path(root);output=Path(output);w=read_witness(root)
    result={'schema':1,'replicates':n,'seed':seed,'witness_sha256':hashlib.sha256((root/'data/witnesses/cluster_statistics.json').read_bytes()).hexdigest(),'score_intervals':{},'contrasts':{},'near':{},
            'main_family':[],'beers_family':[],'aligned':{},'glm':{},'inference':'conditional entity/reply working model'}
    def key(model,ds,contrast):return '|'.join((model,ds,contrast))
    for model in w['models']:
        for ds in ('hospital','movies','beers'):
            entries={c:w['main'][model][ds][c] for c in 'OFWS'}
            groups=GROUPS if model==w['models'][0] else ('identity',)
            for g in groups:
                draws=draw_series(entries,ds,g,n,seed)
                for c,e in entries.items():
                    result['score_intervals'][key(model,ds,c)+'|'+g]=interval_record(draws[c],score(e,g))
                if g!='identity':continue
                for a,b in [('F','W'),('W','S'),('O','S'),('O','W'),('O','F')]:
                    d=score(entries[a],g)-score(entries[b],g)
                    s=None if draws[a] is None or draws[b] is None else draws[a]-draws[b]
                    rec=interval_record(s,d);rec['diff']=round(score(entries[a],g),4)-round(score(entries[b],g),4)
                    rec['p']=None if s is None else centered_p(s,d)
                    result['contrasts'][key(model,ds,a+'-'+b)]=rec
            for a,b in [('hospital','F-W'),('hospital','W-S'),('hospital','O-S'),('movies','F-W'),('movies','O-W')]:
                if a==ds:result['main_family'].append(key(model,ds,b))
            if ds=='beers':result['beers_family'].append(key(model,ds,'O-S'))
        result['near'][model]={ds:{s:rate_interval(events,n,seed) for s,events in settings.items()}
                                for ds,settings in w['near'][model].items()}
    for name in ('main_family','beers_family'):
        fam=result[name];assert len(fam)==(40 if name=='main_family' else 8)
        for k,q in zip(fam,holm([result['contrasts'][k]['p'] for k in fam])):
            result['contrasts'][k]['holm_p']=q;result['contrasts'][k]['significant']=q<.05
    # Movies complete-reply sensitivity, with its full 40-comparison family.
    model=w['models'][2];entries=w['main'][model]['movies'];sensitivity=[]
    allkeys=set(range(entries['O']['replies']))
    for contrast in ('F-W','O-W'):
        a,b=contrast.split('-');badA=set(entries[a]['incomplete']);badB=set(entries[b]['incomplete'])
        ka=allkeys-badA;kb=allkeys-badB
        if a!='F':ka=kb=ka&kb
        ea,eb=subset(entries[a],ka),subset(entries[b],kb)
        rng=np.random.default_rng(seed);ra=rng.exponential(1.,size=(n,len(ka)))
        rb=rng.exponential(1.,size=(n,len(kb))) if a=='F' else ra
        sa=series(ea,'identity',None,ra);sb=series(eb,'identity',None,rb)
        d=score(ea,'identity')-score(eb,'identity');rec=interval_record(sa-sb,d)
        rec.update(diff=round(score(ea,'identity'),4)-round(score(eb,'identity'),4),p=centered_p(sa-sb,d),
                   chunks=[len(ka),len(kb)])
        result['glm'][contrast]={'all':result['contrasts'][key(model,'movies',contrast)],'complete':rec}
    family=[result['contrasts'][k]['p'] for k in result['main_family']]
    for contrast,item in result['glm'].items():family[result['main_family'].index(key(model,'movies',contrast))]=item['complete']['p']
    adjusted=holm(family)
    result['glm_family_complete']=dict(zip(result['main_family'],adjusted))
    for c,item in result['glm'].items():item['complete']['holm_p']=result['glm_family_complete'][key(model,'movies',c)]
    # Aligned LLM and the same three fixed Baran runs share input weights.
    model=w['models'][0]
    for ds,entries in w['aligned'].items():
        ne=max(e['entities'] for e in entries['llm'].values());rng=np.random.default_rng(seed)
        ew=None if ds=='movies' else rng.exponential(1.,size=(n,ne))
        rw=rng.exponential(1.,size=(n,entries['llm']['O']['replies']))
        frw=rng.exponential(1.,size=(n,entries['llm']['F']['replies']))
        for c,e in entries['llm'].items():
            for g in GROUPS:
                weights=frw if c=='F' else rw
                draw=series(e,g,ew,weights);result['aligned'][ds+'|'+c+'|'+g]=interval_record(draw,score(e,g))
                bs=[series(run,g,ew,weights) for run in entries['baran'][c]]
                mean=sum(score(run,g) for run in entries['baran'][c])/len(bs)
                result['aligned'][ds+'|'+c+'|'+g]['llm_minus_baran']=interval_record(draw-np.mean(bs,axis=0),score(e,g)-mean)
                result['aligned'][ds+'|'+c+'|'+g]['baran_mean']=mean
        print('aligned',ds,flush=True)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    return result
