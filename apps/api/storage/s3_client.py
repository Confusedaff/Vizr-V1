"""
Object storage client — S3-compatible, pointed at MinIO by default (see
docker-compose.yml's `minio` service) so the whole stack is self-contained
with no AWS account required. Works unchanged against real AWS S3 by
just changing S3_ENDPOINT_URL/credentials, since MinIO implements the S3
API.

Design: videos are rendered to local/volume disk first
(debug_runs/{job_id}/05_render/media/...), then uploaded here as a
distinct pipeline step. This keeps the render path free of network
dependencies (a render that succeeds shouldn't fail the job just because
object storage had a hiccup — that's a distinct, separately-retryable
failure mode, reflected in JobStatus.UPLOADING existing separately from
JobStatus.RENDERING).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") or None
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "aiviz_minio_admin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "aiviz_minio_secret")
S3_BUCKET = os.environ.get("S3_BUCKET", "aiviz-videos")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
# How long a presigned GET URL remains valid. Videos aren't re-signed on
# every request (see video_url caching in tasks.py) — this only bounds
# how long a given cached URL is usable before a fresh one is needed.
PRESIGNED_URL_EXPIRY_SECONDS = int(os.environ.get("S3_PRESIGNED_URL_EXPIRY_SECONDS", str(7 * 24 * 3600)))


class StorageError(Exception):
    pass


@dataclass
class UploadResult:
    object_key: str
    url: str
    bucket: str


def _get_client():
    # Re-read from the environment at call time rather than relying on
    # the module-level constants captured at import time — this matters
    # for tests that toggle S3_ENDPOINT_URL after this module is first
    # imported (moto needs the *absence* of a custom endpoint_url to
    # intercept requests; a frozen import-time constant would miss that).
    endpoint_url = os.environ.get("S3_ENDPOINT_URL") or None
    kwargs = dict(
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", S3_ACCESS_KEY),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", S3_SECRET_KEY),
        region_name=os.environ.get("S3_REGION", S3_REGION),
        config=BotoConfig(signature_version="s3v4"),
    )
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("s3", **kwargs)


def ensure_bucket_exists(bucket: str = S3_BUCKET) -> None:
    client = _get_client()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=bucket)
        except (ClientError, BotoCoreError) as e:
            raise StorageError(f"Could not create bucket {bucket!r}: {e}") from e
    except BotoCoreError as e:
        raise StorageError(f"Could not reach object storage to check bucket {bucket!r}: {e}") from e


def upload_video(local_path: str | Path, *, job_id: str, bucket: str = S3_BUCKET) -> UploadResult:
    local_path = Path(local_path)
    if not local_path.exists():
        raise StorageError(f"Local video file does not exist: {local_path}")

    object_key = f"renders/{job_id}/{local_path.name}"
    client = _get_client()

    try:
        ensure_bucket_exists(bucket)
        client.upload_file(
            str(local_path), bucket, object_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
    except (ClientError, BotoCoreError) as e:
        raise StorageError(f"Upload failed for job {job_id}: {e}") from e

    url = get_presigned_url(object_key, bucket=bucket)
    return UploadResult(object_key=object_key, url=url, bucket=bucket)


def get_presigned_url(
    object_key: str, *, bucket: str = S3_BUCKET, expires_in: int = PRESIGNED_URL_EXPIRY_SECONDS
) -> str:
    client = _get_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )
    except (ClientError, BotoCoreError) as e:
        raise StorageError(f"Could not generate presigned URL for {object_key}: {e}") from e


def delete_video(object_key: str, *, bucket: str = S3_BUCKET) -> None:
    client = _get_client()
    try:
        client.delete_object(Bucket=bucket, Key=object_key)
    except (ClientError, BotoCoreError) as e:
        raise StorageError(f"Could not delete {object_key}: {e}") from e
