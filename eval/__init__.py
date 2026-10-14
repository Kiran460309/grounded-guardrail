"""eval — dataset loader, baselines, metrics."""
from pathlib import Path
import json

DATASET_PATH = Path(__file__).parent / "data" / "dataset.json"

def load_dataset(split: str = "all") -> list[dict]:
    raw = json.loads(DATASET_PATH.read_text())
    if split == "all":
        return raw
    return [c for c in raw if c["split"] == split]
