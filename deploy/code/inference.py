"""
Serverless inference handler.

SageMaker's Python inference toolkit calls model_fn once per container and then
input_fn -> predict_fn -> output_fn per request.

The export ran with nms:False, so the model emits raw [1, 5, 8400] and this file
owns letterboxing and NMS. onnxruntime only -- no torch, no ultralytics -- which
is what keeps the serverless cold start short.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

IMGSZ = 640
CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD = float(os.environ.get("IOU_THRESHOLD", "0.45"))


def model_fn(model_dir: str):
    """Load the ONNX session and the class names beside it."""
    model_dir = Path(model_dir)

    onnx_files = sorted(model_dir.glob("*.onnx"))
    if not onnx_files:
        raise RuntimeError(f"no .onnx under {model_dir}")

    # single-core serverless: extra intra-op threads only add contention
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    session = ort.InferenceSession(
        str(onnx_files[0]),
        options,
        providers=["CPUExecutionProvider"],
    )

    names = ["car_plate"]
    metadata = sorted(model_dir.glob("*.metadata.json"))
    if metadata:
        names = json.loads(metadata[0].read_text()).get("names", names)

    return {"session": session, "names": names}


def input_fn(body, content_type: str):
    """Accept a raw image, or JSON carrying a base64 one."""
    if content_type in ("image/jpeg", "image/png", "application/x-image"):
        return Image.open(io.BytesIO(body)).convert("RGB")

    if content_type == "application/json":
        import base64

        payload = json.loads(body)
        if "image" not in payload:
            raise ValueError("json payload needs an 'image' key (base64)")
        raw = base64.b64decode(payload["image"])
        return Image.open(io.BytesIO(raw)).convert("RGB")

    raise ValueError(f"unsupported content type: {content_type}")


def letterbox(image: Image.Image) -> tuple[np.ndarray, float, int, int]:
    """
    Resize preserving aspect ratio, pad to IMGSZ, return the transform.

    The scale and pad offsets come back so predict_fn can map boxes to the
    original image; getting this wrong is the usual source of boxes that look
    plausible but sit slightly off the object.
    """
    width, height = image.size
    scale = min(IMGSZ / width, IMGSZ / height)
    new_w, new_h = round(width * scale), round(height * scale)

    resized = image.resize((new_w, new_h), Image.BILINEAR)

    # 114 is the ultralytics pad value; matching it keeps train/serve identical
    canvas = Image.new("RGB", (IMGSZ, IMGSZ), (114, 114, 114))
    pad_x, pad_y = (IMGSZ - new_w) // 2, (IMGSZ - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    tensor = np.asarray(canvas, dtype=np.float32) / 255.0
    tensor = tensor.transpose(2, 0, 1)[np.newaxis, ...]
    return np.ascontiguousarray(tensor), scale, pad_x, pad_y


def nms(boxes: np.ndarray, scores: np.ndarray) -> list[int]:
    """Greedy IoU suppression. Boxes are xyxy."""
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size:
        current = order[0]
        keep.append(int(current))
        if order.size == 1:
            break

        rest = order[1:]
        xx1 = np.maximum(x1[current], x1[rest])
        yy1 = np.maximum(y1[current], y1[rest])
        xx2 = np.minimum(x2[current], x2[rest])
        yy2 = np.minimum(y2[current], y2[rest])

        overlap = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = overlap / (areas[current] + areas[rest] - overlap)
        order = rest[iou <= IOU_THRESHOLD]

    return keep


def predict_fn(image: Image.Image, model: dict) -> dict:
    tensor, scale, pad_x, pad_y = letterbox(image)

    session = model["session"]
    outputs = session.run(None, {session.get_inputs()[0].name: tensor})

    # [1, 4+nc, 8400] -> [8400, 4+nc]; rows are cx, cy, w, h, then class scores
    predictions = outputs[0][0].T

    class_scores = predictions[:, 4:]
    confidence = class_scores.max(axis=1)
    class_ids = class_scores.argmax(axis=1)

    hits = confidence >= CONF_THRESHOLD
    if not hits.any():
        return {"detections": []}

    predictions = predictions[hits]
    confidence = confidence[hits]
    class_ids = class_ids[hits]

    cx, cy, w, h = predictions[:, 0], predictions[:, 1], predictions[:, 2], predictions[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)

    # undo the letterbox: strip padding, then rescale to the source image
    boxes[:, [0, 2]] -= pad_x
    boxes[:, [1, 3]] -= pad_y
    boxes /= scale

    width, height = image.size
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height)

    names = model["names"]
    detections = [
        {
            "box": [round(float(v), 2) for v in boxes[i]],
            "confidence": round(float(confidence[i]), 4),
            "class_id": int(class_ids[i]),
            "class_name": names[int(class_ids[i])]
            if int(class_ids[i]) < len(names)
            else str(class_ids[i]),
        }
        for i in nms(boxes, confidence)
    ]

    return {"detections": detections}


def output_fn(prediction: dict, accept: str) -> tuple[str, str]:
    return json.dumps(prediction), "application/json"
