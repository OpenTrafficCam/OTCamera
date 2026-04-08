import logging

import boto3
from botocore.exceptions import ClientError

from config import S3Config
from domain.upload import Upload


logger = logging.getLogger(__name__)


class S3Upload(Upload):

    def __init__(self, config: S3Config):
        self.config = config

    def upload(self, file_path) -> None:
        """Upload a file to an S3-compatible object storage."""

        session = boto3.Session(
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
            region_name=self.config.region
        )

        client: boto3 = session.client("s3", endpoint_url=self.config.endpoint_url)

        try:
            client.upload_file(file_path, self.config.bucket, file_path)
        except ClientError as e:
            logging.error(e)
