"""Apply checked manuscript captions and display projections after statistical replay."""
import importlib.util
import json
from pathlib import Path
import shutil


def apply_current_display(root, output, *, config=None, projection_source=None,
                          explanatory_source=None):
    root, output = Path(root), Path(output)
    config = Path(config or root / 'code/config/paper_presentation.json')
    projection_source = Path(projection_source or root / 'code/src/paper_presentation.py')
    explanatory_source = Path(explanatory_source or root / 'results/tables/publicverification.tex')
    from tools.cluster_display import apply_cluster_statistics,body_digest
    specs=json.loads(config.read_text())['sources']
    changed=('decomposition.tex','counts.tex','beers.tex','near.tex')
    already_current=all(body_digest(root,(output/'tables'/name).read_text())==specs[name]['body_sha256'] for name in changed)
    cluster={'already_projected':True} if already_current else apply_cluster_statistics(root,output)
    spec = importlib.util.spec_from_file_location('submission_presentation',projection_source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CONFIG = config
    # This source is an explanatory navigation table, not an experimental result.
    shutil.copyfile(explanatory_source,output / 'tables/publicverification.tex')
    names = json.loads(config.read_text())['sources']
    inputs = {name:(output / 'tables' / name).read_text() for name in names}
    projected = module.project_tables(inputs)
    for name,text in projected.items():
        (output / 'tables' / name).write_text(text)
    return {'full_table_sources':len(names),'table_source_count':len(projected),'cluster_statistics':cluster,
            'new_experiments':False}
