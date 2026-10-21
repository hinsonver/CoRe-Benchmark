"""Keep historical witness provenance limited to the original scoring namespace."""
from pathlib import Path


def restrict_scoring_modules(overlay, original_code):
    """Remove only new .py display/runtime modules from a task-owned temporary overlay."""
    overlay = Path(overlay)
    allowed = {name for name in original_code if name.startswith('code/src/') and name.endswith('.py')}
    if not allowed:
        raise ValueError('Historical scoring requires a nonempty original-code allowlist')
    removed = []
    for path in sorted((overlay / 'code/src').glob('*.py')):
        name = path.relative_to(overlay).as_posix()
        if name not in allowed:
            path.unlink()
            removed.append(name)
    return removed
