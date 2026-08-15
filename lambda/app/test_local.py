"""
Test with TestClient

Usage:
    python -m test_local
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
IMAGE = REPO / "data" / "raw" / "audi_a5_with_license_plate_43.png"

PATH = "/v1/models/yolo-car-plate"
client = TestClient(app.app)


def show(label: str, status: int, body: dict) -> dict:
    print(f"{label:<28} {status}  {json.dumps(body)[:180]}")
    return body


def call(label: str, method: str, path: str, body: dict | None = None) -> dict:
    response = client.request(method, path, json=body)
    parsed = response.json() if response.content else {}
    return show(label, response.status_code, parsed)


def main() -> None:
    call("GET readiness", "GET", PATH)

    # main.js renders detail directly, so it has to stay a string on the error
    # paths -- FastAPI's default validation body is a list and would show as
    # "[object Object]" in the page
    for label, body in (
        ("POST no body", {}),
        ("POST bad shape", {"instances": [{}]}),
    ):
        detail = call(label, "POST", f"{PATH}:predict", body)["detail"]
        assert isinstance(detail, str), f"{label}: detail is {type(detail).__name__}"

    b64 = base64.b64encode(IMAGE.read_bytes()).decode()

    body = call(
        "POST predict conf=0.25",
        "POST",
        f"{PATH}:predict",
        {"instances": [{"image": {"b64": b64}, "conf": 0.25}]},
    )

    # the same image at a threshold above its best score must come back empty,
    # which is what proves the slider is actually applied
    high = call(
        "POST predict conf=0.99",
        "POST",
        f"{PATH}:predict",
        {"instances": [{"image": {"b64": b64}, "conf": 0.99}]},
    )

    assert body["predictions"][0]["count"] == 1, "expected one plate at 0.25"
    assert high["predictions"][0]["count"] == 0, "expected none at 0.99"

    detection = body["predictions"][0]["detections"][0]
    assert set(detection["box"]) == {"x1", "y1", "x2", "y2"}, (
        f"unexpected box shape: {detection['box']}"
    )

    # through the Lambda adapter, which is what actually runs in the container
    event = {
        "version": "2.0",
        "rawPath": PATH,
        "rawQueryString": "",
        "requestContext": {
            "http": {
                "method": "GET",
                "path": PATH,
                "sourceIp": "127.0.0.1",
            }
        },
        "headers": {},
        "isBase64Encoded": False,
    }
    response = app.handler(event, None)
    show("mangum GET readiness", response["statusCode"], json.loads(response["body"]))
    assert response["statusCode"] == 200, "mangum did not route the Function URL event"

    print("\nall assertions passed")


if __name__ == "__main__":
    main()
