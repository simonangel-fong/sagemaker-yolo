"""
FastAPI app between the browser and the SageMaker endpoint.
uvicorn app:app --port 8080
Endpoints:
    GET  /v1/models/{model}           readiness + class names
    POST /v1/models/{model}:predict   detections
"""

from __future__ import annotations

import json
import os

import boto3
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

ENDPOINT = os.environ.get("ENDPOINT_NAME", "sagemaker-yolo-dev")
MODEL = os.environ.get("MODEL_NAME", "sagemaker-yolo-dev")
IMGSZ = int(os.environ.get("IMGSZ", "640"))
CLASSES = json.loads(os.environ.get("CLASSES", '["car_plate"]'))
ALLOW_ORIGIN = os.environ.get("ALLOW_ORIGIN", "*")

# Max request size: serverless SageMaker 6MB
MAX_B64_BYTES = 6 * 1024 * 1024

runtime = boto3.client("sagemaker-runtime")

app = FastAPI(title="sagemaker-yolo proxy", docs_url=None, redoc_url=None)

# middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOW_ORIGIN],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type"],
    max_age=3600,
)


# ##############################
# Request / response shapes
# ##############################
class Image(BaseModel):
    b64: str


class Instance(BaseModel):
    image: Image
    # the endpoint filters on its own CONF_THRESHOLD env var, which is fixed at
    # deploy time; the slider in the UI moves per request, so re-filter here
    conf: float = 0.0


class PredictRequest(BaseModel):
    instances: list[Instance] = Field(min_length=1)


@app.exception_handler(RequestValidationError)
async def malformed_body(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "expected instances[0].image.b64"},
    )


# ##############################
# Routes
# ##############################
@app.get("/v1/models/{model}")
def readiness(model: str) -> dict:
    return {"name": MODEL, "classes": CLASSES, "imgsz": IMGSZ}


@app.post("/v1/models/{model}:predict")
def predict(model: str, body: PredictRequest) -> dict:
    instance = body.instances[0]
    b64 = instance.image.b64

    if len(b64) > MAX_B64_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"image is {len(b64) / 1024 / 1024:.1f} MB base64, over the "
                f"{MAX_B64_BYTES / 1024 / 1024:.0f} MB limit -- resize before sending"
            ),
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
        raise HTTPException(status_code=502, detail=f"model error: {err}")
    except Exception as err:  # noqa: BLE001 - surface the reason to the browser
        raise HTTPException(status_code=502, detail=f"endpoint call failed: {err}")

    detections = [
        {
            # returns box as [x1, y1, x2, y2];
            "box": dict(zip(("x1", "y1", "x2", "y2"), det["box"])),
            "class_name": det["class_name"],
            "class_id": det["class_id"],
            "confidence": det["confidence"],
        }
        for det in result.get("detections", [])
        if det["confidence"] >= instance.conf
    ]

    return {"predictions": [{"detections": detections, "count": len(detections)}]}


# Lambda entrypoint.
handler = Mangum(app, lifespan="off")
