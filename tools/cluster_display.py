"""Apply entity/reply statistics to table inputs, derived data and plotted intervals."""
from pathlib import Path
import csv,hashlib,importlib.util,json,os,re,subprocess,sys

NAMES=['DeepSeek-V4-Pro','Qwen3.8-Max','GLM-5.3','GPT-6.1-Sol','Qwen2.5-7B','Llama-3.1-8B','Qwen2.5-14B','Qwen2.5-32B']
TAGS=['custom_deepseek_deepseek-v4-pro','custom_qwen_qwen3.8-max','custom_z-ai_glm-5.3','openai_gpt-6.1-sol','local_qwen2.5-7b','local_llama3.1-8b','local_qwen2.5-14b','local_qwen2.5-32b-awq']

def load_module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def body_digest(root,text):
    p=load_module(root/'code/src/paper_presentation.py','presentation_body')
    a,b=p.caption_span(text);body=text[:a]+text[b:]
    body=body.replace(p._GROUPED_HEADER,p._MODEL_HEADER)
    return hashlib.sha256(body.encode()).hexdigest()

def data_rows(text):
    result=[]
    for line in text.splitlines():
        if any(line.strip().startswith(n+' &') for n in NAMES):
            result.append([v.strip() for v in line.strip().removesuffix(r'\\').split('&')])
    if len(result)!=8:raise ValueError('Expected eight model rows')
    return result

def replace_rows(text,rows):
    it=iter(rows);out=[]
    for line in text.splitlines():
        if any(line.strip().startswith(n+' &') for n in NAMES):out.append('    '+' & '.join(next(it))+r' \\')
        else:out.append(line)
    return '\n'.join(out)+'\n'

def mark(cell,rec):
    return cell.replace(r'$^\dagger$','')+(r'$^\dagger$' if rec['significant'] else '')

def table(label,columns,header,rows):
    return ('\\begin{table}[t]\n  \\caption{Repair results.}\n  \\label{'+label+'}\n  \\small\n'
            '  \\setlength{\\tabcolsep}{3.5pt}\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}'+columns+'@{}}\n'
            '    \\toprule\n'+header+'\n    \\midrule\n'+
            '\n'.join('    '+' & '.join(row)+r' \\' for row in rows)+'\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def rewrite_tables(root,output,stats,*,calibrate=False):
    cfgpath=root/'code/config/paper_presentation.json';cfg=json.loads(cfgpath.read_text())
    sources=cfg['sources'];names=('decomposition.tex','counts.tex','beers.tex','near.tex')
    for name in names:
        p=output/'tables'/name;text=p.read_text();actual=body_digest(root,text)
        expected=sources[name].get('input_body_sha256',sources[name]['body_sha256'])
        if actual!=expected:raise ValueError('Unexpected table input: '+name)
        if name=='decomposition.tex':
            rows=data_rows(text)
            for tag,row in zip(TAGS,rows):
                for col,ds,contrast in [(5,'hospital','F-W'),(6,'hospital','W-S'),(7,'hospital','O-S'),(12,'movies','F-W'),(13,'movies','O-W')]:
                    row[col]=mark(row[col],stats['contrasts'][f'{tag}|{ds}|{contrast}'])
            text=replace_rows(text,rows)
        elif name=='counts.tex':
            # Input rows use abbreviated labels; retain all count and Movies-test cells.
            lines=[l for l in text.splitlines() if len(l.split('&'))==7 and ('DeepSeek &' in l or any(l.strip().startswith(n) for n in ('Qwen3.8 &','GLM-5.3 &','GPT-6.1 &','Qwen-7B &','Llama-8B &','Qwen-14B &','Qwen-32B &')))]
            if len(lines)!=8:raise ValueError('Count rows changed')
            rows=[[v.strip() for v in l.strip().removesuffix(r'\\').split('&')] for l in lines]
            rows=[[r[i] for i in (0,1,2,4,5,6)] for r in rows]
            header=r'    & \multicolumn{2}{c}{Hospital, W vs S} & \multicolumn{3}{c}{Movies, O vs W} \\'+'\n'+r'    \cmidrule(lr){2-3}\cmidrule(l){4-6}'+'\n'+r'    Model & W/S & Chunks & O/W & Chunks & $p$ \\'
            text=table('tab:counts','lrr rrr',header,rows)
        elif name=='beers.tex':
            rows=data_rows(text)
            for tag,row in zip(TAGS,rows):row[5]=mark(row[5],stats['contrasts'][f'{tag}|beers|O-S'])
            rows=[r[:7] for r in rows]
            text=table('tab:beers','lcccccr',r'    Model & O & F & W & S & O$-$S & Cities repaired \\',rows)
        else:
            rows=data_rows(text)
            for tag,row in zip(TAGS,rows):
                for j,prompt in [(2,'standard'),(3,'evidence')]:
                    r=stats['near'][tag]['movies'][f'real|1|{prompt}']
                    row[j]=(f"{r['rate']:.3f} [{r['ci'][0]:.3f}, {r['ci'][1]:.3f}]" if r['interval_available'] else
                            f"{r['rate']:.3f} ({int(r['rewritten'])}/{r['entities']})")
            text=replace_rows(text,rows)
        p.write_text(text)
        if calibrate:
            sources[name]['input_body_sha256']=expected;sources[name]['body_sha256']=body_digest(root,text)
    if calibrate:cfgpath.write_text(json.dumps(cfg,indent=2)+'\n')

def correct_derived(root,output,stats):
    p=output/'derived/scale_summary.json';data=json.loads(p.read_text())
    for name,record in data.items():
        if name not in NAMES:
            for d in record['p2'].values():
                for key in ('memory','entity','spelling','entity_paired'):d[key]['ci']=None
            continue
        tag=TAGS[NAMES.index(name)]
        for ds,d in record['p2'].items():
            for field,contrast in [('memory','O-F'),('entity','F-W'),('spelling','W-S'),('entity_paired','O-W')]:
                rec=stats['contrasts'][f'{tag}|{ds}|{contrast}'];d[field]['ci']=rec['ci'] if rec['interval_available'] else None
                d[field]['interval_kind']=rec['kind']
        for ds,near in record['near'].items():
            for setting,r in stats['near'][tag][ds].items():
                if setting in near:near[setting]=r
        record['beers_city']['words_vs_syllable'].pop('sign_test_p',None)
        record['beers_city']['words_vs_syllable']['interpretation']='descriptive chunk counts'
    p.write_text(json.dumps(data,indent=2)+'\n')
    (output/'derived/aligned_cluster_comparisons.json').write_text(json.dumps(stats['aligned'],indent=2)+'\n')
    p=output/'figures/fig3_aligned.csv';rows=list(csv.DictReader(p.open()))
    for row in rows:
        if row['series']=='Baran, aligned':row['ci_low']=row['ci_high']='';continue
        cond=load_module(root/'code/src/cluster_statistics.py','condition_names').condition_code(row['condition'])
        if row['series'].endswith('zero-shot'):r=stats['score_intervals'][f'{TAGS[0]}|{row["dataset"]}|{cond}|identity']
        else:r=stats['aligned'][f'{row["dataset"]}|{cond}|identity']
        # The score labels remain exactly those of the fixed CSV.
        assert abs(float(row['repair_f1'])-r['point'])<.00051
        row['ci_low'],row['ci_high']=[str(round(x,3)) for x in r['ci']] if r['interval_available'] else ('','')
    with p.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def apply_cluster_statistics(root,output,*,calibrate=False,compute=True):
    root=Path(root);output=Path(output)
    module=load_module(root/'code/src/cluster_statistics.py','cluster_stat_engine')
    path=output/'derived/cluster_statistics.json'
    if compute:stats=module.run(root,path)
    else:
        path.write_bytes((root/'results/derived/cluster_statistics.json').read_bytes());stats=json.loads(path.read_text())
    rewrite_tables(root,output,stats,calibrate=calibrate);correct_derived(root,output,stats)
    env={**os.environ,'CORE_MODE':'public','CORE_ARTIFACT_ROOT':str(root),'CORE_BUILD_DIR':str(output),
        'CORE_FIGURE_DIR':str(output/'figures'),'CORE_CLUSTER_RESULTS':str(path),
        'PYTHONPATH':str(root/'code'),'PYTHONDONTWRITEBYTECODE':'1','MPLCONFIGDIR':str(output/'.mplconfig')}
    subprocess.run([sys.executable,'-c','from src import figures as f; f.fig1(); f.fig3(); f.fig4(); f.fig6(); f.fig7()'],
                   cwd=root,env=env,check=True)
    return {'replicates':stats['replicates'],'main_family':len(stats['main_family']),
            'beers_family':len(stats['beers_family']),'new_model_calls':0}
