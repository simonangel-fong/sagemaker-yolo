"""
Lambda between the browser and the SageMaker endpoint.

Exists because the browser cannot call SageMaker directly: the runtime API
requires SigV4-signed requests, and signing in JS would mean shipping
credentials to the client.

This function does no image work. It unwraps the request, forwards the base64
image to the endpoint, and reshapes the reply into what web/js/main.js already
expects -- that contract predates this deployment, so the translation lives
here rather than in the browser.

Routes (Function URL, so routing is by path here, not by API Gateway):
    GET  /v1/models/yolo-car-plate           readiness + class names
    POST /v1/models/yolo-car-plate:predict   detections
"""

from __future__ import annotations

import json
import os

import boto3

ENDPOINT = os.environ.get("ENDPOINT_NAME", "sagemaker-yolo-dev-yolo")
MODEL = os.environ.get("MODEL_NAME", "yolo-car-plate")
IMGSZ = int(os.environ.get("IMGSZ", "640"))
CLASSES = json.loads(os.environ.get("CLASSES", '["car_plate"]'))

# API Gateway caps a request at 10 MB and serverless SageMaker at 6 MB; base64
# inflates by ~4/3, so anything past this cannot reach the endpoint intact.
MAX_B64_BYTES = 6 * 1024 * 1024

runtime = boto3.client("sagemaker-runtime")

CORS = {
    "Access-Control-Allow-Origin": os.environ.get("ALLOW_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def reply(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS},
        "body": json.dumps(body),
    }


def handler(event, context):
    request = event.get("requestContext", {}).get("http", {})
    method = request.get("method", "GET")
    path = request.get("path", "/")

    # the browser preflights the POST because the page is served from a
    # different origin than the function
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    if method == "GET":
        return reply(200, {"name": MODEL, "classes": CLASSES, "imgsz": IMGSZ})

    if method != "POST":
        return reply(405, {"detail": f"method not allowed: {method}"})

    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return reply(400, {"detail": "body is not valid json"})

    instances = payload.get("instances")
    if not instances:
        return reply(400, {"detail": "expected an 'instances' array"})

    instance = instances[0]
    b64 = (instance.get("image") or {}).get("b64")
    if not b64:
        return reply(400, {"detail": "expected instances[0].image.b64"})

    if len(b64) > MAX_B64_BYTES:
        return reply(
            413,
            {
                "detail": (
                    f"image is {len(b64) / 1024 / 1024:.1f} MB base64, over the "
                    f"{MAX_B64_BYTES / 1024 / 1024:.0f} MB limit -- resize before sending"
                )
            },
        )

    try:
        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps({"image": b64}),
        )
        result = json.loads(response["Body"].read())
    except runtime.exceptions.ModelError as err:
        return reply(502, {"detail": f"model error: {err}"})
    except Exception as err:  # noqa: BLE001 - surface the reason to the browser
        return reply(502, {"detail": f"endpoint call failed: {err}"})

    # the endpoint filters on its own CONF_THRESHOLD env var, which is fixed at
    # deploy time; the slider in the UI moves per request, so re-filter here
    conf = float(instance.get("conf", 0.0))

    detections = [
        {
            # handler returns box as [x1, y1, x2, y2]; main.js destructures
            # {x1, y1, x2, y2}, so reshape rather than touch the browser code
            "box": dict(zip(("x1", "y1", "x2", "y2"), det["box"])),
            "class_name": det["class_name"],
            "class_id": det["class_id"],
            "confidence": det["confidence"],
        }
        for det in result.get("detections", [])
        if det["confidence"] >= conf
    ]

    return reply(
        200,
        {"predictions": [{"detections": detections, "count": len(detections)}]},
    )
