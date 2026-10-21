"""Run TabClean (third_party/TabClean) with an OpenAI-compatible relay instead of OpenAI.

Every agent uses one model (default: DeepSeek-V4-Pro through the relay in .env, thinking
disabled). The relay's base URL and key are read from .env inside this process and handed to
TabClean as OPENAI_API_KEY / base_url, never printed. Work files go to results/e4/tabclean/.

Usage: .venv-tabclean/bin/python scripts/run_tabclean.py --dataset rayyan [--model deepseek/deepseek-v4-pro]
       (dataset = a folder of third_party/TabClean/datasets, or --csv/--gt paths)
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
TC = ROOT / "third_party" / "TabClean"

ap = argparse.ArgumentParser()
ap.add_argument("--dataset")
ap.add_argument("--csv")
ap.add_argument("--gt")
ap.add_argument("--model", default="deepseek/deepseek-v4-pro")
ap.add_argument("--tag", default="")
a, rest = ap.parse_known_args()
csv = a.csv or str(TC / "datasets" / a.dataset / "dirty.csv")
gt = a.gt or str(TC / "datasets" / a.dataset / "clean.csv")
name = (a.tag or a.dataset or Path(csv).parent.name)

# Keep the relay's key in this process only: TabClean runs LLM-written code in subprocesses
# that inherit os.environ, so no secret goes into the environment.
secrets = dotenv_values(ROOT / ".env")
api_key, base_url = secrets["CUSTOM_API_KEY"], secrets["CUSTOM_BASE_URL"]
for k in list(secrets) + ["OPENAI_API_KEY"]:
    os.environ.pop(k, None)
work = ROOT / "results" / "e4" / "tabclean" / name
work.mkdir(parents=True, exist_ok=True)
os.environ["TABCLEAN_WORK_DIR"] = str(work)
os.environ["TABCLEAN_RESULTS_DIR"] = str(work / "results")
os.environ["TABCLEAN_PRIVATE_DIR"] = str(work / "private")

sys.path.insert(0, str(TC))
import config  # noqa: E402  (must be patched before pipeline imports its names)
for k in ("MODEL_DIAGNOSE", "MODEL_REVIEW", "MODEL_STRATEGIZE", "MODEL_CODE", "MODEL_DEBUGGER"):
    setattr(config, k, a.model)
config.WORK_DIR = str(work)
import pipeline  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402


def make_llm(model, temperature=0.7):
    return ChatOpenAI(model=model, api_key=api_key, base_url=base_url,
                      temperature=temperature, extra_body={"thinking": {"type": "disabled"}}, timeout=600)


pipeline._make_llm = make_llm
# The relay reports cached_tokens as null, which TabClean's cost tracker cannot subtract.
_record = pipeline.cost_tracker.record


def safe_record(*args, **kwargs):
    try:
        return _record(*args, **kwargs)
    except TypeError:
        return None


pipeline.cost_tracker.record = safe_record
import main as tc_main  # noqa: E402
tc_main.WORK_DIR = str(work)
sys.argv = ["main.py", "--csv", csv, "--gt", gt, *rest]
os.chdir(work)
tc_main.main()
