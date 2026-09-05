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
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") or None
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "vizr_minio_admin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "vizr_minio_secret")
S3_BUCKET = os.environ.get("S3_BUCKET", "vizr-videos")
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


def _remux_for_web_playback(local_path: Path) -> Path:
    """Manim's file writer (via PyAV) concatenates partial movie files by
    remuxing packets with no `movflags=+faststart`, so the mp4's `moov`
    atom (the index) lands at the *end* of the file. Players that read
    the whole file from local disk (VLC, ffprobe) don't care, but a
    browser <video> element streaming from a presigned S3/MinIO URL
    generally needs the moov atom up front to start decoding at all —
    without it you get "No video with supported format and MIME type
    found" even though the codec (libx264/yuv420p) is perfectly valid.
    This does a fast, lossless remux (-c copy, no re-encode) to move the
    moov atom to the front before upload. Returns the original path
    unchanged if ffmpeg isn't available or the remux fails, so a missing
    ffmpeg binary degrades to the old (sometimes-unplayable) behavior
    instead of failing the whole upload.
    """
    fixed_fd, fixed_name = tempfile.mkstemp(suffix=".mp4", dir=str(local_path.parent))
    os.close(fixed_fd)
    fixed_path = Path(fixed_name)

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(local_path),
                "-c", "copy",
                "-movflags", "+faststart",
                str(fixed_path),
            ],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fixed_path.unlink(missing_ok=True)
        return local_path

    if result.returncode != 0 or not fixed_path.exists() or fixed_path.stat().st_size == 0:
        fixed_path.unlink(missing_ok=True)
        return local_path

    fixed_path.replace(local_path)
    return local_path


def upload_video(local_path: str | Path, *, job_id: str, bucket: str = S3_BUCKET) -> UploadResult:
    local_path = Path(local_path)
    if not local_path.exists():
        raise StorageError(f"Local video file does not exist: {local_path}")

    local_path = _remux_for_web_playback(local_path)

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
    # Presigned URLs are consumed by the *browser*, not by this container,
    # so they must be signed against a host the browser can resolve.
    # S3_ENDPOINT_URL (e.g. http://minio:9000) is the Docker-internal
    # hostname used for server-to-server calls (upload_file, head_bucket,
    # etc.) and is never reachable from outside the compose network.
    # S3_PUBLIC_ENDPOINT_URL overrides just the host used for signing,
    # defaulting to localhost:9000 (MinIO's published port) for local dev.
    # Only set explicitly when S3_ENDPOINT_URL itself is configured (i.e.
    # we're actually pointed at MinIO, not plain AWS/moto) — this mirrors
    # _get_client's endpoint handling so tests using moto's default AWS
    # endpoint resolution are unaffected.
    kwargs = dict(
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", S3_ACCESS_KEY),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", S3_SECRET_KEY),
        region_name=os.environ.get("S3_REGION", S3_REGION),
        config=BotoConfig(signature_version="s3v4"),
    )
    if os.environ.get("S3_ENDPOINT_URL"):
        kwargs["endpoint_url"] = os.environ.get("S3_PUBLIC_ENDPOINT_URL") or "http://localhost:9000"
    client = boto3.client("s3", **kwargs)
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