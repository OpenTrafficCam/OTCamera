import os
from pathlib import Path
from shutil import copyfile
from typing import Any

import boto3
import pytest
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError

from OTCamera.config import S3Config
from OTCamera.controller.backlog import Backlog
from OTCamera.controller.backlog_controller import BacklogController
from OTCamera.domain.events import EventBus, RecordingSplit
from OTCamera.plugin.upload.s3_upload import S3Upload

EXAMPLE_VIDEOS_FOLDER = Path(__file__).parent.parent / "data" / "example_videos_folder"

assert EXAMPLE_VIDEOS_FOLDER.is_dir()

EXAMPLE_VIDEOS_PATHS = set(EXAMPLE_VIDEOS_FOLDER.glob("*.h264"))


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


@pytest.fixture
def s3client(local_s3_config: S3Config) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=local_s3_config.endpoint_url,
        aws_access_key_id=local_s3_config.access_key,
        aws_secret_access_key=local_s3_config.secret_key,
        region_name=local_s3_config.region,
        config=Boto3Config(
            retries={"total_max_attempts": local_s3_config.retry_max_attempts}
        ),
    )


@pytest.fixture
def reset_s3_bucket(s3client: Any, local_s3_config: S3Config) -> None:
    bucket_name = local_s3_config.bucket

    try:
        paginator = s3client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            objects = page.get("Contents", [])
            if objects:
                s3client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                )
        s3client.delete_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            raise

    s3client.create_bucket(Bucket=bucket_name)


KEY_PREFIX = "project/site/camera"


@pytest.mark.integration
def test_s3_upload(
    reset_s3_bucket: Any, s3client: Any, local_s3_config: S3Config, tmp_path: Path
) -> None:
    upload = S3Upload(
        s3client, bucket_name=local_s3_config.bucket, key_prefix=KEY_PREFIX
    )

    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    backlog = Backlog(video_dir=video_dir, video_format="h264", min_free_bytes=0)

    event_bus = EventBus()
    backlog_controller = BacklogController(
        event_bus=event_bus, upload=upload, backlog=backlog
    )

    for example_video in EXAMPLE_VIDEOS_PATHS:
        recorded = video_dir / example_video.name
        copyfile(example_video, recorded)
        event_bus.publish(RecordingSplit(str(recorded)))

    assert backlog.size() == len(EXAMPLE_VIDEOS_PATHS)

    # Drain the backlog on this thread so that the assertions below cannot race
    # the worker.
    for _ in EXAMPLE_VIDEOS_PATHS:
        backlog_controller.run_once()

    assert backlog.size() == 0
    assert backlog.uploaded_total == len(EXAMPLE_VIDEOS_PATHS)

    response = s3client.list_objects_v2(Bucket=local_s3_config.bucket)

    keys = {el["Key"] for el in response["Contents"]}

    expected = {f"{KEY_PREFIX}/{p.name}" for p in EXAMPLE_VIDEOS_PATHS}

    assert keys == expected
