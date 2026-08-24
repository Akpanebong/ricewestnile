import json
from pathlib import Path


ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"


def get_latest_meta():
    files = sorted(ARTIFACT_DIR.glob("meta_*.json"))
    if not files:
        return None
    with files[-1].open() as f:
        return json.load(f)
