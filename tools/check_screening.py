"""Check all archived screening dependencies before regeneration; no API imports."""
import json
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "code"))
from src.screening import check_all
print(json.dumps(check_all(root), ensure_ascii=False))
