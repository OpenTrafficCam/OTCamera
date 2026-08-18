from pathlib import Path
from unittest.mock import patch

import pytest

from OTCamera.config import Config, OTCloudSettings, RabbitMqConfig
from OTCamera.plugin.upload_notifier.store_backed_notifier import StoreBackedNotifier
from OTCamera.plugin.upload_notifier.upload_notification_provider import (
    UploadNotificationProvider,
)


@pytest.fixture
def rabbitmq_config() -> Config:
    return Config(
        notification="rabbitmq",
        rabbitmq=RabbitMqConfig(
            host="localhost",
            exchange="uploads",
            routing_key="file_uploaded",
            queue_name="notifications",
        ),
        ot_cloud=OTCloudSettings(camera_id=1, project_id=1, site_id=1),
    )


def test_provide_returns_none_when_no_notification_configured() -> None:
    assert UploadNotificationProvider.provide(Config()) is None


def test_provide_returns_a_running_store_backed_notifier(
    rabbitmq_config: Config, tmp_path: Path
) -> None:
    with patch(
        "OTCamera.plugin.upload_notifier.upload_notification_provider._NOTICE_DIR",
        tmp_path / "notices",
    ):
        notifier = UploadNotificationProvider.provide(rabbitmq_config)

    try:
        assert isinstance(notifier, StoreBackedNotifier)
        assert notifier.is_running
    finally:
        if notifier is not None:
            notifier.close()

    assert not notifier.is_running
