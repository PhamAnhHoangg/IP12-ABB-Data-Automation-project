"""Small helper to send ZED + YOLO results to n8n without slowing the camera loop.

Copy this file next to the ZED/YOLO script and use it like this:

    from n8n_reporter import N8nReporter

    reporter = N8nReporter(
        url="http://localhost:5678/webhook/ip12/yolo",
        run_code="run-001",
        model_version="yolo11n_boxes_v1",
    )

    # inside the camera loop, after YOLO + ZED have produced objects:
    reporter.add(box_id=obj_id, cls="box_small", confidence=0.91,
                 x=x1, y=y1, w=w, h=h, frame_id=frame_nr)

    # at the end:
    reporter.close()

How it works:
- add() only puts the detection in a queue, so it takes microseconds.
- A background thread sends batches every `flush_every` seconds.
- If n8n is not reachable, the batch is appended to `fallback_file`
  (one JSON per line), so no data is lost. Re-send it later with
  `python n8n_reporter.py --resend <file> --url <webhook url>`.

Standard library only: no pip install needed.
"""
import json
import queue
import threading
import time
import urllib.error
import urllib.request


class N8nReporter:
    def __init__(self, url, run_code, model_version,
                 flush_every=2.0, max_batch=200,
                 fallback_file="n8n_unsent.jsonl", timeout=5):
        self.url = url
        self.run_code = run_code
        self.model_version = model_version
        self.flush_every = flush_every
        self.max_batch = max_batch
        self.fallback_file = fallback_file
        self.timeout = timeout
        self.sent = 0
        self.failed = 0
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def add(self, cls, confidence, box_id=None, frame_id=None,
            x=None, y=None, w=None, h=None):
        """Queue one detection. Never blocks the camera loop."""
        self._q.put({
            "class": str(cls), "confidence": float(confidence),
            "box_id": None if box_id is None else str(box_id),
            "frame_id": frame_id,
            "x": x, "y": y, "w": w, "h": h,
        })

    def close(self):
        """Send what is left, then stop the background thread."""
        self._stop.set()
        self._thread.join(timeout=self.timeout + 5)
        print(f"[n8n] sent {self.sent} detections, {self.failed} saved to {self.fallback_file}")

    # ---- internals ----
    def _run(self):
        while not self._stop.is_set():
            self._stop.wait(self.flush_every)
            self._flush()
        self._flush()

    def _flush(self):
        while True:
            batch = []
            while len(batch) < self.max_batch:
                try:
                    batch.append(self._q.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return
            payload = {"run_code": self.run_code,
                       "model_version": self.model_version,
                       "detections": batch}
            if post_json(self.url, payload, self.timeout):
                self.sent += len(batch)
            else:
                self.failed += len(batch)
                with open(self.fallback_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload) + "\n")


def post_json(url, payload, timeout=5):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f"[n8n] send failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Re-send detections saved while n8n was offline")
    ap.add_argument("--resend", required=True, help="the .jsonl fallback file")
    ap.add_argument("--url", default="http://localhost:5678/webhook/ip12/yolo")
    args = ap.parse_args()
    ok = bad = 0
    with open(args.resend, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                if post_json(args.url, json.loads(line)):
                    ok += 1
                else:
                    bad += 1
    print(f"re-sent {ok} batches, {bad} failed")
