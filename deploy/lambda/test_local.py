"""
Run the Lambda handler locally against the real endpoint.

Invokes app.handler with synthetic Function URL events, so the routing, the
reshaping and the error paths are exercised before any Terraform exists.

Usage:
    python -m deploy.lambda.test_local
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
IMAGE = REPO / "data" / "raw" / "audi_a5_with_license_plate_43.png"


def event(method: str, path: str, body: dict | None = None) -> dict:
    return {
        "requestContext": {"http": {"method": method, "path": path}},
        "body": json.dumps(body) if body is not None else None,
    }


def show(label: str, response: dict) -> dict:
    body = json.loads(response["body"]) if response["body"] else {}
    print(f"{label:<28} {response['statusCode']}  {json.dumps(body)[:180]}")
    return body


def main() -> None:
    path = "/v1/models/yolo-car-plate"

    show("GET readiness", app.handler(event("GET", path), None))
    show("OPTIONS preflight", app.handler(event("OPTIONS", path), None))
    show("POST no body", app.handler(event("POST", path, {}), None))
    show(
        "POST bad shape",
        app.handler(event("POST", path, {"instances": [{}]}), None),
    )

    b64 = base64.b64encode(IMAGE.read_bytes()).decode()

    body = show(
        "POST predict conf=0.25",
        app.handler(
            event("POST", path, {"instances": [{"image": {"b64": b64}, "conf": 0.25}]}),
            None,
        ),
    )

    # the same image at a threshold above its best score must come back empty,
    # which is what proves the slider is actually applied
    high = show(
        "POST predict conf=0.99",
        app.handler(
            event("POST", path, {"instances": [{"image": {"b64": b64}, "conf": 0.99}]}),
            None,
        ),
    )

    assert body["predictions"][0]["count"] == 1, "expected one plate at 0.25"
    assert high["predictions"][0]["count"] == 0, "expected none at 0.99"

    box = body["predictions"][0]["detections"][0]["box"]
    assert set(box) == {"x1", "y1", "x2", "y2"}, f"unexpected box shape: {box}"

    print("\nall assertions passed")


if __name__ == "__main__":
    main()
