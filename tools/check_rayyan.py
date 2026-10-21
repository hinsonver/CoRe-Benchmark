"""Offline version-bound Rayyan replay; never request PubMed or model outputs."""
import json
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "code"))
from src.rayyan_replay import replay
print(json.dumps(replay(root), ensure_ascii=False))
