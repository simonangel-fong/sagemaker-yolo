"""
S3 transfer helpers, on boto3.

`aws s3 sync` is a CLI-only feature, so the skip-unchanged comparison it does
for free is implemented here: an object is re-transferred only when its size
differs or the source is newer.
"""

from __future__ import annotations

from pathlib import Path

import boto3


def split_uri(uri: str) -> tuple[str, str]:
    """s3://bucket/some/prefix -> ("bucket", "some/prefix")"""
    if not uri.startswith("s3://"):
        raise ValueError(f"not an s3 uri: {uri}")
    bucket, _, key = uri[5:].partition("/")
    return bucket, key.strip("/")


def list_objects(uri: str, client=None) -> dict[str, dict]:
    """Map of key -> {size, modified} under a prefix."""
    client = client or boto3.client("s3")
    bucket, prefix = split_uri(uri)

    objects: dict[str, dict] = {}
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        for obj in page.get("Contents", []):
            # skip the zero-byte markers terraform creates for prefixes
            if obj["Key"].endswith("/"):
                continue
            objects[obj["Key"]] = {
                "size": obj["Size"],
                "modified": obj["LastModified"],
            }
    return objects


def download(uri: str, dest: Path, client=None) -> dict[str, int]:
    """
    Mirror an S3 prefix into `dest`, skipping unchanged files.

    Returns counts of downloaded and skipped objects.
    """
    client = client or boto3.client("s3")
    bucket, prefix = split_uri(uri)
    dest.mkdir(parents=True, exist_ok=True)

    downloaded = skipped = 0
    for key, meta in list_objects(uri, client).items():
        target = dest / Path(key).relative_to(prefix)

        # same size means unchanged, for immutable image/label data
        if target.exists() and target.stat().st_size == meta["size"]:
            skipped += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(bucket, key, str(target))
        downloaded += 1

    return {"downloaded": downloaded, "skipped": skipped}


def upload(source: Path, uri: str, delete: bool = False, client=None) -> dict[str, int]:
    """
    Mirror a local directory to an S3 prefix, skipping unchanged files.

    `delete` removes objects that no longer exist locally, so a re-split under
    a different seed does not leave the previous partition behind.
    """
    client = client or boto3.client("s3")
    bucket, prefix = split_uri(uri)

    existing = list_objects(uri, client)
    uploaded = skipped = 0
    seen: set[str] = set()

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue

        key = f"{prefix}/{path.relative_to(source).as_posix()}"
        seen.add(key)

        current = existing.get(key)
        if current and current["size"] == path.stat().st_size:
            skipped += 1
            continue

        client.upload_file(str(path), bucket, key)
        uploaded += 1

    removed = 0
    if delete:
        stale = [k for k in existing if k not in seen]
        # delete_objects caps at 1000 keys per call
        for i in range(0, len(stale), 1000):
            chunk = stale[i : i + 1000]
            client.delete_objects(
                Bucket=bucket, Delete={"Objects": [{"Key": k} for k in chunk]}
            )
            removed += len(chunk)

    return {"uploaded": uploaded, "skipped": skipped, "removed": removed}


def upload_files(paths: list[Path], uri: str, client=None) -> list[str]:
    """Upload individual files into a prefix. Returns the destination URIs."""
    client = client or boto3.client("s3")
    bucket, prefix = split_uri(uri)

    written = []
    for path in paths:
        key = f"{prefix}/{path.name}"
        client.upload_file(str(path), bucket, key)
        written.append(f"s3://{bucket}/{key}")
    return written
