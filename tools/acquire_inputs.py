"""Opt-in, version/hash-pinned TabClean input acquisition outside the public tree.

Downloading verifies bytes, not permission to rehost them. Public replay does
not use this tool. --fetch requires an explicit acknowledgement of source terms.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
BASE='https://raw.githubusercontent.com/Wangyibo321/TabClean/ae292b6ff8118c8786cd7c97364e9a8a07f00b62'
ASSETS={'rayyan-inputs':{
    'dirty.csv':{'url':BASE+'/datasets/rayyan/dirty.csv','sha256':'61aa71010693eb551122521e56b3997c0d366e3aa81848585631dfbef80d7309'},
    'clean.csv':{'url':BASE+'/datasets/rayyan/clean.csv','sha256':'f4ab0c3bdfa6a13eeea51d16482ec8cd395acbf59b595e3ea6ef0b34bc448744'}}}


def unsafe_link(path):
    path=Path(path).absolute()
    aliases={Path('/var'):Path('/private/var'),Path('/tmp'):Path('/private/tmp')}
    return any(p.is_symlink() and not(p in aliases and p.resolve()==aliases[p]) for p in [path,*path.parents])


def validate_destination(root,dest):
    root=Path(root).resolve();raw=Path(dest).absolute()
    if unsafe_link(raw):raise ValueError('Destination symlink forbidden')
    dest=raw.resolve()
    if dest==root or root in dest.parents:raise ValueError('Destination must be outside the public repository')
    if dest.exists():raise FileExistsError('Destination exists; no overwrite')
    return dest


def import_pair(asset,source,dest,root=ROOT):
    dest=validate_destination(root,dest);source=Path(source)
    spec=ASSETS[asset]
    for name,item in spec.items():
        p=source/name
        if not p.is_file() or unsafe_link(p):raise ValueError('Missing/unsafe input: '+name)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Input hash mismatch: '+name)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='core-input-',dir=dest.parent) as temp:
        staged=Path(temp)/'pair';staged.mkdir()
        for name in spec:shutil.copyfile(source/name,staged/name)
        if dest.exists() or dest.is_symlink():raise FileExistsError('Destination appeared; no overwrite')
        staged.rename(dest)
    return {'asset':asset,'files_verified':len(spec),'destination':str(dest),'redistribution_authorized':False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Redirect refused; use the pinned source URL')


def fetch(asset,dest,acknowledge=False,root=ROOT):
    validate_destination(root,dest)
    if not acknowledge:raise ValueError('Review source terms and explicitly acknowledge before downloading')
    opener=urllib.request.build_opener(NoRedirect())
    with tempfile.TemporaryDirectory(prefix='core-fetch-') as temp:
        for name,item in ASSETS[asset].items():
            with opener.open(item['url'],timeout=30) as response:
                if response.geturl()!=item['url']:raise ValueError('Source URL changed')
                data=response.read(20_000_001)
            if len(data)>20_000_000:raise ValueError('Input exceeds expected size limit')
            (Path(temp)/name).write_bytes(data)
        return import_pair(asset,Path(temp),dest,root)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('asset',choices=ASSETS)
    ap.add_argument('--destination',type=Path,required=True)
    mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--from-directory',type=Path);mode.add_argument('--fetch',action='store_true')
    ap.add_argument('--acknowledge-source-terms',action='store_true');a=ap.parse_args()
    print(json.dumps(import_pair(a.asset,a.from_directory,a.destination) if a.from_directory else
        fetch(a.asset,a.destination,a.acknowledge_source_terms),indent=2))
