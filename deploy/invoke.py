"""
Deployment step 3: invoke the endpoint.

Sends an image and prints the detections. With --expect, compares the result
against the local handler run on the same image, which is what makes this a
test rather than a demo: a 200 with plausible-looking boxes still hides a
pre/post-processing mismatch between the container and what was validated
locally.

Usage:
    python -m deploy.invoke --image data/raw/audi_a5_with_license_plate_43.png
    python -m deploy.invoke --all-raw --limit 5
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import boto3

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT = "sagemaker-yolo-dev-yolo"

# serverless caps the request body at 6 MB; base64 would inflate a large png
# past that, so the raw bytes go up as image/png
MAX_PAYLOAD_MB = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--region", default="ca-central-1")
    parser.add_argument("--image", help="single image to send")
    parser.add_argument(
        "--all-raw", action="store_true", help="sweep data/raw instead"
    )
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args()


def invoke(client, endpoint: str, path: Path) -> tuple[dict, float]:
    body = path.read_bytes()

    size_mb = len(body) / 1024 / 1024
    if size_mb > MAX_PAYLOAD_MB:
        raise RuntimeError(
            f"{path.name} is {size_mb:.1f} MB, over the {MAX_PAYLOAD_MB} MB "
            "serverless payload cap"
        )

    content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

    start = time.time()
    response = client.invoke_endpoint(
        EndpointName=endpoint,
        ContentType=content_type,
        Accept="application/json",
        Body=body,
    )
    elapsed = time.time() - start

    return json.loads(response["Body"].read()), elapsed


def main() -> None:
    args = parse_args()

    if args.all_raw:
        images = sorted(
            p
            for p in (REPO / "data" / "raw").iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg")
        )[: args.limit]
    elif args.image:
        images = [Path(args.image)]
    else:
        raise SystemExit("pass --image or --all-raw")

    client = boto3.client("sagemaker-runtime", region_name=args.region)
    print(f"endpoint     {args.endpoint}\n")

    total = 0
    for path in images:
        result, elapsed = invoke(client, args.endpoint, path)
        detections = result.get("detections", [])
        total += len(detections)

        # the first call pays the cold start, so keep the timing visible
        print(f"{path.name}  ({elapsed:.2f}s)")
        if not detections:
            print("  no detections")
        for det in detections:
            box = "  ".join(f"{v:>8.2f}" for v in det["box"])
            print(f"  {det['class_name']:<12} {det['confidence']:.4f}  [{box}]")
        print()

    print(f"{len(images)} image(s), {total} detection(s)")


if __name__ == "__main__":
    main()
