import os
import io
from minio import Minio
from autonomous_media.config import settings

def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False
    )

def ensure_bucket(bucket_name: str) -> None:
    client = get_minio_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

def upload_file(bucket_name: str, object_name: str, file_path: str) -> None:
    client = get_minio_client()
    ensure_bucket(bucket_name)
    client.fput_object(bucket_name, object_name, file_path)

def download_file(bucket_name: str, object_name: str, file_path: str) -> None:
    client = get_minio_client()
    client.fget_object(bucket_name, object_name, file_path)

def put_object_data(bucket_name: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    client = get_minio_client()
    ensure_bucket(bucket_name)
    data_stream = io.BytesIO(data)
    client.put_object(bucket_name, object_name, data_stream, len(data), content_type=content_type)

def get_object_data(bucket_name: str, object_name: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(bucket_name, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
