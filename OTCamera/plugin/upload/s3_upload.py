import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config as Boto3Config
from boto3.s3.transfer import TransferConfig

from OTCamera.domain.upload import Upload
from OTCamera.config import S3Config


logger = logging.getLogger(__name__)


# Disable boto3-internal split and threading, let us handle concurrency
TRANSFER_CONFIG = TransferConfig(
    multipart_threshold=100 * 1024 * 1024 * 1024,  # effectively disable multipart (100GB)
    max_concurrency=1,                             # no internal threads
    use_threads=False,
)


class S3Upload(Upload):
    """Upload files to an S3-compatible object storage.

    Thread-safe: each call to ``upload`` is independent and uses no shared
    mutable state beyond the boto3 client, which is itself thread-safe for
    concurrent ``upload_file`` calls.  Internal boto3 multipart splitting and
    its own threading are disabled via ``TRANSFER_CONFIG`` so that concurrency
    is controlled entirely by the caller.
    """

    def __init__(self, s3client: Any, bucket_name: str):
        """
        Args:
            s3client: A boto3 S3 client instance.
            bucket_name: Name of the target S3 bucket.
        """
        self.client = s3client
        self.bucket_name = bucket_name

    @classmethod
    def from_config(cls, s3_config: S3Config) -> "S3Upload":
        """Create an ``S3Upload`` instance from an ``S3Config``.

        Args:
            s3_config: Configuration object containing endpoint URL, credentials,
                region, bucket name, and retry settings.

        Returns:
            A fully configured ``S3Upload`` instance.
        """
        client = boto3.client(
            "s3",
            endpoint_url=s3_config.endpoint_url,
            aws_access_key_id=s3_config.access_key,
            aws_secret_access_key=s3_config.secret_key,
            region_name=s3_config.region,
            config=Boto3Config(
                retries={"total_max_attempts": s3_config.retry_max_attempts}
            ),
        )

        return cls(s3client=client, bucket_name=s3_config.bucket)

    def upload(self, file_path) -> None:
        """Upload a single file to the configured S3 bucket.

        The file is stored under a key equal to its basename.

        Args:
            file_path: Path to the local file to upload.
        """
        try:
            key = Path(file_path).name

            self.client.upload_file(file_path, self.bucket_name, key, Config=TRANSFER_CONFIG)
        except Exception as e:
            logging.error(e)

    def is_available(self):
        """Always returns ``True`` for S3; connectivity errors surface during
        ``upload`` instead.
        """
        return True
