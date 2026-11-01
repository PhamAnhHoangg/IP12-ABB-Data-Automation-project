"""Send fake YOLO detections to n8n, to test the pipeline without a camera.

Usage:
    python send_test_detection.py                 # 5 random detections, test webhook
    python send_test_detection.py --count 20
    python send_test_detection.py --prod          # use the active (production) webhook

Only uses the Python standard library, so no pip install is needed.
WP1 can copy send_detections() into the real YOLO script later.
"""
import argparse
import json
import random
import urllib.error
import urllib.request

TEST_URL = "http://localhost:5678/webhook-test/ip12/yolo"   # while "Listen for test event" is on
PROD_URL = "http://localhost:5678/webhook/ip12/yolo"        # after the workflow is activated


def send_detections(url, detections, run_code="run-test", model_version="v0-test"):
    payload = {"run_code": run_code, "model_version": model_version, "detections": detections}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode()


def fake_detection(i):
    return {
        "frame_id": i,
        "box_id": f"box_{i:03d}",
        "class": random.choice(["box_small", "box_medium", "box_large"]),
        "confidence": round(random.uniform(0.35, 0.99), 3),
        "x": random.randint(0, 1280), "y": random.randint(0, 720),
        "w": random.randint(40, 300), "h": random.randint(40, 300),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--prod", action="store_true")
    ap.add_argument("--url", help="override the webhook URL")
    args = ap.parse_args()

    url = args.url or (PROD_URL if args.prod else TEST_URL)
    dets = [fake_detection(i) for i in range(1, args.count + 1)]
    try:
        status, body = send_detections(url, dets)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} from {url}")
        print(e.read().decode()[:500])
        if e.code == 404:
            print("\nWebhook is not listening. Fix:")
            print("  Test URL: click 'Execute workflow' in n8n first, then run this within 2 minutes.")
            print("  Prod URL (--prod): the workflow must be published/active.")
            print("  Or copy the URL from the YOLO Webhook node and pass it with --url")
        raise SystemExit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach {url}: {e.reason}. Is n8n running? (docker compose ps)")
        raise SystemExit(1)
    print(f"HTTP {status} from {url}")
    print(body[:1000])
