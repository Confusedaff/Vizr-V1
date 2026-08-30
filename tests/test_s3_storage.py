"""
Tests for apps/api/storage/s3_client.py using moto to mock the S3 API
surface. This validates the actual boto3 call semantics (bucket
creation, upload, presigned URL generation, deletion, error handling)
against a real (mocked) S3-protocol server — moto implements the AWS S3
API faithfully, and MinIO also implements the S3 API, so exercising
these calls here gives real confidence the same code works against
MinIO in docker-compose, even though this test suite can't reach a live
MinIO instance directly (network sandboxing) or verify MinIO-specific
non-AWS extensions.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("S3_BUCKET", "test-bucket")
# Ensure no custom endpoint is set for these tests — moto intercepts the
# standard AWS endpoint resolution, not an arbitrary custom endpoint_url
# (see apps/api/storage/s3_client.py::_get_client for why this matters).
os.environ.pop("S3_ENDPOINT_URL", None)


@pytest.fixture
def s3_mock():
    with mock_aws():
        yield


@pytest.fixture
def sample_video_file():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"fake mp4 bytes for testing")
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def test_ensure_bucket_exists_creates_bucket(s3_mock):
    from apps.api.storage import s3_client

    s3_client.ensure_bucket_exists("test-bucket-1")
    client = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in client.list_buckets()["Buckets"]]
    assert "test-bucket-1" in buckets


def test_ensure_bucket_exists_idempotent(s3_mock):
    from apps.api.storage import s3_client

    s3_client.ensure_bucket_exists("test-bucket-2")
    s3_client.ensure_bucket_exists("test-bucket-2")  # should not raise


def test_upload_video_success(s3_mock, sample_video_file):
    from apps.api.storage import s3_client

    result = s3_client.upload_video(sample_video_file, job_id="job123", bucket="test-bucket-3")
    assert result.object_key == f"renders/job123/{sample_video_file.name}"
    assert result.bucket == "test-bucket-3"
    assert result.url  # presigned URL was generated

    client = boto3.client("s3", region_name="us-east-1")
    obj = client.get_object(Bucket="test-bucket-3", Key=result.object_key)
    assert obj["Body"].read() == b"fake mp4 bytes for testing"


def test_upload_video_missing_file_raises(s3_mock):
    from apps.api.storage import s3_client

    with pytest.raises(s3_client.StorageError):
        s3_client.upload_video("/nonexistent/path.mp4", job_id="job123", bucket="test-bucket-4")


def test_unreachable_endpoint_raises_storage_error_not_botocore_error(sample_video_file, monkeypatch):
    """Regression test: a connectivity failure (wrong/unreachable
    endpoint) must surface as StorageError, not an uncaught
    botocore.exceptions.EndpointConnectionError. This was a real bug:
    ClientError and BotoCoreError are sibling exception types (neither
    subclasses the other), so catching only ClientError let connectivity
    failures crash past the intended error boundary — found while testing
    the upload-failure path against an intentionally-unreachable host."""
    from apps.api.storage import s3_client

    monkeypatch.setenv("S3_ENDPOINT_URL", "http://nonexistent-host-for-testing.invalid:9000")
    with pytest.raises(s3_client.StorageError):
        s3_client.upload_video(sample_video_file, job_id="job999", bucket="unreachable-bucket")


def test_get_presigned_url_returns_url(s3_mock, sample_video_file):
    from apps.api.storage import s3_client

    result = s3_client.upload_video(sample_video_file, job_id="job456", bucket="test-bucket-5")
    url = s3_client.get_presigned_url(result.object_key, bucket="test-bucket-5")
    assert url.startswith("http")
    assert result.object_key in url


def test_delete_video_removes_object(s3_mock, sample_video_file):
    from apps.api.storage import s3_client

    result = s3_client.upload_video(sample_video_file, job_id="job789", bucket="test-bucket-6")
    s3_client.delete_video(result.object_key, bucket="test-bucket-6")

    client = boto3.client("s3", region_name="us-east-1")
    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(Bucket="test-bucket-6", Key=result.object_key)
