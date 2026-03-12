"""MinIO object storage client."""

from __future__ import annotations

import io
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.config import settings

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
        )
        if not _client.bucket_exists(settings.MINIO_BUCKET):
            _client.make_bucket(settings.MINIO_BUCKET)
    return _client


def upload_bytes(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = get_minio_client()
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def upload_file(object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    client = get_minio_client()
    client.fput_object(settings.MINIO_BUCKET, object_name, file_path, content_type=content_type)
    return object_name


def download_bytes(object_name: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    from datetime import timedelta

    client = get_minio_client()
    return client.presigned_get_object(
        settings.MINIO_BUCKET, object_name, expires=timedelta(hours=expires_hours)
    )


def delete_object(object_name: str) -> None:
    client = get_minio_client()
    client.remove_object(settings.MINIO_BUCKET, object_name)
