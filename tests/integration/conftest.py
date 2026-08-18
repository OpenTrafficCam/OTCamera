"""Fixtures for the integration tests that talk to a local S3 server."""

import os
from pathlib import Path
from typing import Any, Iterator

import boto3
import pytest
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError

from OTCamera.config import S3Config

EXAMPLE_VIDEOS_FOLDER = Path(__file__).parent.parent / "data" / "example_videos_folder"

assert EXAMPLE_VIDEOS_FOLDER.is_dir()

EXAMPLE_VIDEOS_PATHS = set(EXAMPLE_VIDEOS_FOLDER.glob("*.h264"))

KEY_PREFIX = "project/site/camera"


@pytest.fixture
def local_s3_config() -> S3Config:
    HOST = os.getenv("OTC_TEST_S3_HOST", "127.0.0.1")
    PORT = os.getenv("OTC_TEST_S3_PORT", 9000)
    return S3Config(
        endpoint_url=f"http://{HOST}:{PORT}",
        access_key="rustfsadmin",
        secret_key="rustfsadmin",
        bucket="test",
    )


def make_s3client(config: S3Config) -> Any:
    """Return a boto3 client for the given settings.

    Args:
        config (S3Config): The settings to build the client from.
    """
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region,
        config=Boto3Config(
            connect_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
            retries={"total_max_attempts": 1},
        ),
    )


@pytest.fixture
def s3client(local_s3_config: S3Config) -> Any:
    return make_s3client(local_s3_config)


def delete_bucket(s3client: Any, bucket: str) -> None:
    """Delete a bucket and everything in it, if it is there at all.

    Args:
        s3client: The boto3 S3 client to use.
        bucket (str): Name of the bucket to delete.
    """
    try:
        paginator = s3client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            objects = page.get("Contents", [])
            if objects:
                s3client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                )
        s3client.delete_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            raise


@pytest.fixture
def reset_s3_bucket(s3client: Any, local_s3_config: S3Config) -> None:
    delete_bucket(s3client, local_s3_config.bucket)
    s3client.create_bucket(Bucket=local_s3_config.bucket)


@pytest.fixture
def missing_s3_bucket(s3client: Any, local_s3_config: S3Config) -> Iterator[None]:
    """Make sure the configured bucket does not exist during the test."""
    delete_bucket(s3client, local_s3_config.bucket)

    yield

    delete_bucket(s3client, local_s3_config.bucket)


def keys_in_bucket(s3client: Any, bucket: str) -> set[str]:
    """Return the keys currently stored in a bucket.

    Args:
        s3client: The boto3 S3 client to use.
        bucket (str): Name of the bucket to list.
    """
    response = s3client.list_objects_v2(Bucket=bucket)
    return {el["Key"] for el in response.get("Contents", [])}


def body_of(s3client: Any, bucket: str, key: str) -> bytes:
    """Return the stored bytes of one object.

    Args:
        s3client: The boto3 S3 client to use.
        bucket (str): Name of the bucket holding the object.
        key (str): Key the object is stored under.
    """
    return bytes(s3client.get_object(Bucket=bucket, Key=key)["Body"].read())
