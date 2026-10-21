"""Inspect bundled data or install an exact, separately supplied historical archive."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def unsafe_link(path):
    path=Path(path).absolute()
    aliases={Path('/var'):Path('/private/var'),Path('/tmp'):Path('/private/tmp')}
    return any(p.is_symlink() and not(p in aliases and p.resolve()==aliases[p]) for p in [path,*path.parents])


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def status(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / 'data/manifests/SUBMISSION_DATA.json').read_text())
    historical = manifest['historical']
    return {
        'included_tables':sorted(p.name for p in (root / 'data/final').glob('*')
                                 if p.is_dir() and (p / 'clean.csv').is_file()),
        'historical':{k:historical[k] for k in
                      ('archive_filename','sha256','file_count','publication_status')},
        'upstream_snapshots':manifest.get('upstream_snapshots',[]),
        'model_calls':False,'network_requests':False,
    }


def install(root, archive, destination):
    """Verify all bytes before writing; never install historical data into the repository."""
    root = Path(root).resolve()
    target = Path(destination)
    if unsafe_link(target):
        raise ValueError('Historical destination symlink forbidden')
    resolved = target.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError('Historical data destination must be outside the repository')
    if target.exists() or target.is_symlink():
        raise FileExistsError('Destination already exists; no overwrite: ' + str(target))
    archive = Path(archive)
    spec = json.loads((root / 'data/manifests/SUBMISSION_DATA.json').read_text())['historical']
    if digest(archive) != spec['sha256']:
        raise ValueError('Historical archive hash mismatch')
    expected = spec['files']
    if len(expected) != spec['file_count']:
        raise ValueError('Historical file count mismatch')
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Historical archive has duplicate members')
        for info in source.infolist():
            name = info.filename
            relative = PurePosixPath(name)
            if (relative.is_absolute() or '..' in relative.parts or '\\' in name
                    or name != relative.as_posix() or info.is_dir()):
                raise ValueError('Historical archive has unsafe member: ' + name)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Historical archive has symlink member: ' + name)
        if set(names) != set(expected) | {'BUNDLE.json'}:
            raise ValueError('Historical archive members differ from the exact manifest')
        metadata = json.loads(source.read('BUNDLE.json'))
        if metadata.get('schema_version') != 1 or metadata.get('files') != expected:
            raise ValueError('Historical archive metadata differs from the exact manifest')
        for name, expected_digest in expected.items():
            if hashlib.sha256(source.read(name)).hexdigest() != expected_digest:
                raise ValueError('Historical member hash mismatch: ' + name)
        # Preflight completed: write into a new staging directory and rename only
        # after every entry is installed. Failed validation has created no output.
        resolved.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.core-history-', dir=resolved.parent))
        try:
            for name in names:
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.open(name) as reader, path.open('xb') as writer:
                    shutil.copyfileobj(reader, writer)
            if resolved.exists() or resolved.is_symlink():
                raise FileExistsError('Destination appeared during installation; no overwrite')
            stage.rename(resolved)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return {'installed':str(resolved),'files_verified':len(expected),
            'archive_sha256':spec['sha256'],'redistribution_authorized':False,
            'model_calls':False,'network_requests':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='List included tables and the separate historical archive')
    command = commands.add_parser('install', help='Install an exact local archive outside the repository')
    command.add_argument('--archive', type=Path, required=True)
    command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = status() if args.command == 'status' else install(ROOT,args.archive,args.output)
    except (OSError,ValueError,zipfile.BadZipFile) as exc:
        parser.exit(2, str(exc)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
