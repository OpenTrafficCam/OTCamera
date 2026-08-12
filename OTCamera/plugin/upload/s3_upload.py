import logging
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

from OTCamera.domain.upload import S3UploadResult, Upload
from OTCamera.plugin.upload.exceptions import FileUploadError

logger = logging.getLogger(__name__)


def _read_client_error_details(error: ClientError) -> tuple[str | None, int | None]:
    """Read the error code and HTTP status out of a boto3 `ClientError`.

    Both parts can be absent, for example when the request never reached the
    server, so neither is assumed to be present.

    Args:
        error (ClientError): The exception raised by boto3.

    Returns:
        tuple[str | None, int | None]: The error code and HTTP status, each None
            when the response did not carry it.
    """
    response = error.response or {}
    error_code = response.get("Error", {}).get("Code")
    status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return error_code, status_code


class S3Upload(Upload):
    """Upload files to an S3-compatible object storage.

    Thread-safe: each call to `upload` is independent and uses no shared
    mutable state beyond the boto3 client, which is itself thread-safe.
    Each file is sent as one single PUT request, so there is no internal
    splitting or threading and concurrency is controlled entirely by the
    caller.
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

    def upload(self, file_path: Path) -> S3UploadResult:
        """Upload a single file to the configured S3 bucket.

        The file is stored under the key ``{key_prefix}/{filename}`` when a
        prefix is set, or just ``{filename}`` otherwise. It is sent as one
        single PUT request, so a refusal from the server surfaces directly
        with its error code and HTTP status.

        The failure is described in the raised error rather than logged here:
        the caller retries and is the one place that knows how often it has
        already tried.

        Args:
            file_path: Path to the local file to upload.

        Returns:
            S3UploadResult: Where the file was stored.

        Raises:
            FileUploadError: If the upload did not complete, carrying the
                backend's error code and HTTP status when it reported them.
        """
        name = Path(file_path).name
        key = f"{self.key_prefix}/{name}" if self.key_prefix else name

        try:
            with open(file_path, "rb") as body:
                self.client.put_object(Bucket=self.bucket_name, Key=key, Body=body)
        except ClientError as e:
            error_code, status_code = _read_client_error_details(e)
            raise FileUploadError(
                f"S3 refused: {error_code} ({status_code})",
                error_code=error_code,
                status_code=status_code,
            ) from e
        except OSError as e:
            raise FileUploadError(f"Could not read {name}: {e}") from e
        except Exception as e:
            raise FileUploadError(f"Could not upload to S3 bucket. Error: {e}") from e

        logger.info("Uploaded %s", name)
        return S3UploadResult(local_path=file_path, bucket=self.bucket_name, key=key)

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
