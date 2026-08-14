# inference.py
#
# Serverless handler. SageMaker's inference toolkit calls model_fn once per
# container, then input_fn -> predict_fn -> output_fn per request.
#
# YOLO26 is end-to-end: NMS lives in the graph, so the model returns
# [1, 300, 6] rows of x1, y1, x2, y2, confidence, class_id, already filtered,
# in letterboxed pixel coordinates. Postprocessing is a confidence filter and
# undoing the letterbox.
#
# onnxruntime only -- no torch, no ultralytics -- to keep cold starts short.

import io
import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.25"))


def model_fn(model_dir):
    """Load the ONNX session, the class names, and the export image size."""
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

    # the sidecar written by train.py carries the names and the imgsz the
    # model was exported at; letterboxing must use that same size
    with open(model_dir / "model.metadata.json") as f:
        metadata = json.load(f)

    return {
        "session": session,
        "names": metadata["names"],
        "imgsz": metadata["imgsz"],
    }


def input_fn(body, content_type):
    """Accept a raw image, or JSON carrying a base64 one."""
    if content_type in ("image/jpeg", "image/png", "application/x-image"):
        return Image.open(io.BytesIO(body)).convert("RGB")

    if content_type == "application/json":
        import base64

        payload = json.loads(body)
        if "image" not in payload:
            raise ValueError("json payload needs an 'image' key (base64)")
        return Image.open(
            io.BytesIO(base64.b64decode(payload["image"]))
        ).convert("RGB")

    raise ValueError(f"unsupported content type: {content_type}")


def letterbox(image, imgsz):
    """Resize preserving aspect ratio, pad to imgsz, return the transform.

    The scale and pad offsets come back so predict_fn can map boxes to the
    original image.
    """
    width, height = image.size
    scale = min(imgsz / width, imgsz / height)
    new_w, new_h = round(width * scale), round(height * scale)

    # 114 is the ultralytics pad value; matching it keeps train/serve identical
    canvas = Image.new("RGB", (imgsz, imgsz), (114, 114, 114))
    pad_x, pad_y = (imgsz - new_w) // 2, (imgsz - new_h) // 2
    canvas.paste(image.resize((new_w, new_h), Image.BILINEAR), (pad_x, pad_y))

    tensor = np.asarray(canvas, dtype=np.float32) / 255.0
    tensor = tensor.transpose(2, 0, 1)[np.newaxis, ...]

    return np.ascontiguousarray(tensor), scale, pad_x, pad_y


def predict_fn(image, model):
    tensor, scale, pad_x, pad_y = letterbox(image, model["imgsz"])

    session = model["session"]
    outputs = session.run(None, {session.get_inputs()[0].name: tensor})

    # [1, 300, 6] -> [300, 6]: x1, y1, x2, y2, confidence, class_id
    predictions = outputs[0][0]

    keep = predictions[:, 4] >= CONF_THRESHOLD
    if not keep.any():
        return {"detections": []}

    predictions = predictions[keep]

    # undo the letterbox: strip the padding, then rescale to the source image
    boxes = predictions[:, :4].copy()
    boxes[:, [0, 2]] -= pad_x
    boxes[:, [1, 3]] -= pad_y
    boxes /= scale

    width, height = image.size
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height)

    names = model["names"]
    detections = []

    for box, row in zip(boxes, predictions):
        class_id = int(row[5])
        detections.append(
            {
                "box": [round(float(v), 2) for v in box],
                "confidence": round(float(row[4]), 4),
                "class_id": class_id,
                "class_name": names[class_id]
                if class_id < len(names)
                else str(class_id),
            }
        )

    return {"detections": detections}


def output_fn(prediction, accept):
    return json.dumps(prediction), "application/json"
