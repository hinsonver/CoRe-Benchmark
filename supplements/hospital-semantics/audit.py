"""Read-only, independent cell accounting on existing Hospital replies. No API calls."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import re
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
REPO = ROOT / 'build/fresh-review-revision-20261027/work/repo'
IDENTITY = {'ProviderNumber','HospitalName','Address1','City','ZipCode','CountyName','PhoneNumber'}
GEO = {'Address1','City','State','ZipCode','CountyName','PhoneNumber'}
MODELS = ['custom_deepseek_deepseek-v4-pro','custom_qwen_qwen3.8-max',
          'custom_z-ai_glm-5.3','openai_gpt-6.1-sol','local_qwen2.5-7b',
          'local_llama3.1-8b','local_qwen2.5-14b','local_qwen2.5-32b-awq']

def norm(value):
    return re.sub(r'\s*,\s*', ',', ' '.join(str(value).lower().split()))

def parse(text):
    left, right = text.find('{'), text.rfind('}')
    if left < 0 or right <= left:
        return []
    try:
        obj = json.loads(text[left:right+1])
    except json.JSONDecodeError:
        items = []
        for item in re.findall(r'\{[^{}]*\}', text[left:right+1]):
            try:
                items.append(json.loads(item))
            except json.JSONDecodeError:
                pass
        obj = {'corrections': items}
    items = obj.get('corrections', []) if isinstance(obj, dict) else []
    return [p for p in items if isinstance(p,dict) and {'row','column','value'} <= p.keys()]

def table(name):
    result = []
    for which in ('dirty','clean'):
        with (REPO/'data/final'/name/(which+'.csv')).open() as f:
            result.append(list(csv.reader(f)))
    dirty, clean = result
    assert len(dirty)==len(clean) and len(clean)==1001
    columns = clean[0]
    assert all(len(row)==len(columns) for row in dirty[1:]+clean[1:])
    return columns, dirty[1:], clean[1:]

def effective(dirty, columns, predictions):
    edited = {}
    for p in predictions:
        try:
            row = int(p['row'])-1
        except (ValueError,TypeError):
            continue
        col, value = str(p['column']), str(p['value']).strip()
        if 0 <= row < len(dirty) and col in columns:
            j = columns.index(col)
            if norm(value)!=norm(dirty[row][j]):
                edited[row,col] = value
    return edited

def count(dirty, clean, columns, edited, keep=None):
    keep = set(columns) if keep is None else set(keep)
    errors = {(i,col) for i,row in enumerate(clean) for j,col in enumerate(columns)
              if col in keep and dirty[i][j]!=row[j]}
    predictions = {cell:value for cell,value in edited.items() if cell[1] in keep}
    detected = sum(cell in errors for cell in predictions)
    repaired = sum(cell in errors and norm(value)==norm(clean[cell[0]][columns.index(cell[1])])
                   for cell,value in predictions.items())
    return {'errors':len(errors),'predicted':len(predictions),'detected':detected,'repaired':repaired}

def matches_displayed_f1(repaired, predicted, errors, displayed):
    # At exact half-way decimals, harmonic and count formulas can differ by one
    # floating-point ulp. Integer counts remain strictly equal in every check.
    value=2*repaired/(predicted+errors) if predicted+errors else 0.0
    return abs(value-displayed)<=0.000050000001

def write_csv(name, rows):
    assert rows
    with (WORK/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def main():
    oc, od, original = table('hospital')
    variants=['hospital']+[name+suffix for suffix in ('','_s1','_s2')
        for name in ('hospital_fresh','hospital_surrogatewords','hospital_surrogate')]
    relations=[]; edits=[]; runs=[]; failures=[]; sources={}
    for name in variants:
        columns,dirty,clean=table(name)
        for part in ('dirty','clean'):
            path=REPO/'data/final'/name/(part+'.csv')
            sources[str(path.relative_to(REPO))]=hashlib.sha256(path.read_bytes()).hexdigest()
        if 'surrogate' in name:
            nonid=[j for j,c in enumerate(columns) if c not in IDENTITY]
            assert all(a[j]==b[j] for a,b in zip(clean,original) for j in nonid)
            assert all((a[j]!=b[j])==(x[j]!=y[j])
                for a,b,x,y in zip(dirty,clean,od,original) for j in range(len(columns)))
            for col in columns:
                pairs=defaultdict(set)
                for old,new in zip(original,clean):
                    pairs[old[columns.index(col)]].add(new[columns.index(col)])
                relations.append({'dataset':name,'column':col,'identity_column':col in IDENTITY,
                    'distinct_original_values':len(pairs),'one_to_one_consistent':all(len(v)==1 for v in pairs.values()),
                    'injective_mapping':len({v for values in pairs.values() for v in values})==len(pairs),
                    'changed_rows':sum(a[columns.index(col)]!=b[columns.index(col)] for a,b in zip(original,clean)),
                    'state_values':','.join(sorted({r[columns.index('State')] for r in clean}))})
        for model in MODELS:
            path=REPO/'artifacts/raw_outputs/p2'/f'{model}__{name}__k20__spread.json'
            if not path.exists():
                failures.append({'file':path.name,'issue':'missing'});continue
            sources[str(path.relative_to(REPO))]=hashlib.sha256(path.read_bytes()).hexdigest()
            doc=json.loads(path.read_text())
            assert doc['summary']['dataset']==name and doc['summary']['k']==20
            seen=[]; total={g:Counter() for g in ('all','identity','other')}; bycol=defaultdict(Counter)
            for k,chunk in enumerate(doc['chunks']):
                rows=chunk['rows'];seen+=rows
                d=[dirty[i] for i in rows]; c=[clean[i] for i in rows]
                predictions=parse(chunk['output']);p=effective(d,columns,predictions)
                for group,keep in [('all',columns),('identity',IDENTITY),('other',set(columns)-IDENTITY)]:
                    counts=count(d,c,columns,p,keep)
                    assert counts==chunk['counts'][group],(path.name,k,group,counts,chunk['counts'][group])
                    total[group].update(counts)
                for (local,col),value in p.items():
                    i=rows[local];j=columns.index(col);error=dirty[i][j]!=clean[i][j]
                    repair=error and norm(value)==norm(clean[i][j])
                    bycol[col].update({'predicted':1,'detected':int(error),'repaired':int(repair),
                                      'clean_cell_changed':int(not error)})
                    if col not in GEO:continue
                    old=original[i][j] if 'surrogate' in name else ''
                    vocabulary={r[j] for r in original}
                    same_chunk=any(norm(value)==norm(r[j]) for r in d)
                    edits.append({'model':model,'dataset':name,'chunk':k,'global_row_0based':i,
                        'local_row_1based':local+1,'column':col,'dirty':dirty[i][j],'reference':clean[i][j],
                        'output':value,'error':error,'detected':error,'repaired':repair,
                        'clean_cell_changed':not error,'reference_state':clean[i][columns.index('State')],
                        'reference_zip':clean[i][columns.index('ZipCode')],
                        'matches_original_row_value':bool(old) and norm(value)==norm(old),
                        'matches_original_column_vocabulary':norm(value) in {norm(v) for v in vocabulary},
                        'candidate_visible_in_dirty_column':same_chunk,
                        'reason_status':'JSON edit; internal cause not identified',
                        'source_reply':str(path.relative_to(REPO))})
            assert sorted(seen)==list(range(1000)),(name,model,'row coverage')
            for group in total:
                for key,value in total[group].items():
                    assert value==doc['summary'][group][key],(path.name,group,key)
            ident=total['identity']; denominator=ident['errors']+ident['predicted']
            f1=2*ident['repaired']/denominator if denominator else 0
            assert matches_displayed_f1(ident['repaired'],ident['predicted'],ident['errors'],
                                       doc['summary']['identity']['repair_f1']),(path.name,f1)
            runs.append({'model':model,'dataset':name,'chunks':len(doc['chunks']),**dict(ident),
                'repair_f1':doc['summary']['identity']['repair_f1'],'geo_edits':sum(v['predicted'] for c,v in bycol.items() if c in GEO),
                'state_edits':bycol['State']['predicted'],
                'state_clean_edits':bycol['State']['clean_cell_changed'],
                'state_wrong_repairs':bycol['State']['detected']-bycol['State']['repaired'],
                'geo_clean_edits':sum(v['clean_cell_changed'] for c,v in bycol.items() if c in GEO)})
    assert not failures,failures
    write_csv('relations.csv',relations);write_csv('edits.csv',edits);write_csv('runs.csv',runs)
    surrogate=[e for e in edits if 'surrogate' in e['dataset']]
    attention=[e for e in surrogate if not e['repaired']]
    write_csv('uncredited-geographic-edits.csv',attention)
    columns_summary=[]
    for col in sorted(GEO):
        selected=[e for e in surrogate if e['column']==col]
        columns_summary.append({'column':col,'edits':len(selected),
            'repairs':sum(e['repaired'] for e in selected),
            'wrong_error_edits':sum(e['error'] and not e['repaired'] for e in selected),
            'clean_cell_edits':sum(e['clean_cell_changed'] for e in selected)})
    write_csv('surrogate-column-counts.csv',columns_summary)
    source_map={k:v for k,v in sources.items()}
    summary={'runs':len(runs),'chunks':sum(r['chunks'] for r in runs),'paired_variants':6,
        'raw_count_checks':len(runs)*50*3*4,'count_mismatches':0,
        'surrogate_geo_edits':len(surrogate),'surrogate_uncredited_geo_edits':len(attention),
        'surrogate_clean_geo_edits':sum(e['clean_cell_changed'] for e in surrogate),
        'surrogate_state_clean_edits':sum(e['column']=='State' and e['clean_cell_changed'] for e in surrogate),
        'surrogate_state_wrong_repairs':sum(e['column']=='State' and e['error'] and not e['repaired'] for e in surrogate),
        'uncredited_by_column':dict(Counter(e['column'] for e in attention)),
        'old_row_matches_uncredited':sum(e['matches_original_row_value'] for e in attention),
        'no_causal_effect_identified':True,'failures':failures}
    (WORK/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (WORK/'sources.json').write_text(json.dumps(source_map,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo-root',type=Path,default=REPO)
    ap.add_argument('--output',type=Path,default=WORK)
    args=ap.parse_args()
    REPO=args.repo_root.resolve();WORK=args.output.resolve()
    WORK.mkdir(parents=True,exist_ok=True)
    main()
