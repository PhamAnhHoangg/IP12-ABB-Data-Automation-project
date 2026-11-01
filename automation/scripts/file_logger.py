"""Append detections to shared/detections.jsonl for the n8n report.

Usage in the ZED/YOLO/FastAPI code:

    from file_logger import log_detections
    log_detections(objects, run_code="run-001", model_version="v1")

`objects` = a list of dicts (or Pydantic models, e.g. DetectedObject).
One line per call, so the file stays valid even if the program crashes.
Standard library only.
"""
import json
import os
from datetime import datetime

DEFAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared", "detections.jsonl")


def _to_dict(o):
    if hasattr(o, "model_dump"):   # Pydantic v2
        return o.model_dump()
    if hasattr(o, "dict"):         # Pydantic v1
        return o.dict()
    return dict(o)


def log_detections(objects, run_code, model_version, path=DEFAULT_FILE):
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "run_code": run_code,
        "model_version": model_version,
        "detections": [_to_dict(o) for o in objects],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


if __name__ == "__main__":
    # demo: write 2 fake records so the n8n report has something to show
    import random
    colors = ["red", "blue", "green", "yellow"]
    for run in ("run-demo-1", "run-demo-2"):
        objs = [{"box_id": f"box_{i:03d}", "class": "box", "color": random.choice(colors),
                 "priority": random.randint(1, 3), "confidence": round(random.uniform(0.4, 0.99), 2)}
                for i in range(8)]
        log_detections(objs, run_code=run, model_version="v0-demo")
    print("wrote demo data to", os.path.normpath(DEFAULT_FILE))
