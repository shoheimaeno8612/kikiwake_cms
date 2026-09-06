import boto3
import requests

from ..config import Settings
from ..retry import storage_retry


class StorageClient:
    """Cloudflare R2(S3互換)へのアップロード/公開URL経由のダウンロードを扱う。"""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = boto3.client(
            service_name="s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

    @storage_retry()
    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._settings.r2_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def public_url(self, key: str) -> str:
        return f"{self._settings.r2_public_base_url}/{key}"

    @storage_retry()
    def fetch_public(self, key: str) -> bytes:
        """公開URL経由でオブジェクトを取得する(duration再計算のバックフィル用)。"""
        response = requests.get(self.public_url(key))
        response.raise_for_status()
        return response.content
