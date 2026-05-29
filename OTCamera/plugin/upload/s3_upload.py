import logging
from pathlib import Path
from typing import Any

from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

from OTCamera.domain.upload import Upload
from OTCamera.plugin.upload.exceptions import FileUploadError

logger = logging.getLogger(__name__)


# Disable boto3-internal split and threading, let us handle concurrency
TRANSFER_CONFIG = TransferConfig(
    multipart_threshold=100
    * 1024
    * 1024
    * 1024,  # effectively disable multipart (100GB)
    max_concurrency=1,  # no internal threads
    use_threads=False,
)


class S3Upload(Upload):
    """Upload files to an S3-compatible object storage.

    Thread-safe: each call to `upload` is independent and uses no shared
    mutable state beyond the boto3 client, which is itself thread-safe for
    concurrent `upload_file` calls.  Internal boto3 multipart splitting and
    its own threading are disabled via `TRANSFER_CONFIG` so that concurrency
    is controlled entirely by the caller.
    """

    def __init__(
        self,
        s3client: Any,
        bucket_name: str,
        key_prefix: str | None = None,
    ):
        """Create a new `S3Upload` instance.

        Args:
            s3client: A boto3 S3 client instance.
            bucket_name: Name of the target S3 bucket.
            key_prefix: Optional prefix prepended to the filename to form the
                S3 key, e.g. ``project/site/camera``. When omitted the
                filename is used as the key directly.
        """
        self.client = s3client
        self.bucket_name = bucket_name
        self.key_prefix = key_prefix

    def upload(self, file_path: str) -> None:
        """Upload a single file to the configured S3 bucket.

        The file is stored under the key ``{key_prefix}/{filename}`` when a
        prefix is set, or just ``{filename}`` otherwise.

        Args:
            file_path: Path to the local file to upload.
        """
        try:
            name = Path(file_path).name
            key = f"{self.key_prefix}/{name}" if self.key_prefix else name

            self.client.upload_file(
                file_path, self.bucket_name, key, Config=TRANSFER_CONFIG
            )
            logger.info("Uploaded %s", name)
        except Exception as e:
            logger.error("Unexpected error during S3 upload: %s", e)
            raise FileUploadError(f"Could not upload to S3 bucket. Error: {e}") from e

    def is_available(self) -> bool:
        """Perform a quick check to confirm that we are ready to upload files."""
        key = ".preflight_check"

        try:
            self.client.put_object(Bucket=self.bucket_name, Key=key, Body=b"")
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            code = e.response["Error"]["Code"]

            # TODO: Add more speaking log statements for common error codes.
            match code:
                case "NoSuchBucket":
                    logger.error(
                        "S3 is reachable, but the configured bucket does not exist."
                    )
                case _:
                    logger.error(
                        "S3 availability check failed with ClientError: %s" % code
                    )
            return False
        except Exception as e:
            logger.error(e)
            return False

        return True
