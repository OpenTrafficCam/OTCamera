import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from threading import Event as ThreadEvent
from unittest.mock import MagicMock

import pytest
from requests import ConnectionError, HTTPError

from OTCamera.config import Config, HealthchecksConfig
from OTCamera.controller.notification_controller import EventNotificationController
from OTCamera.domain.events import EventBus, S3FileUploaded
from OTCamera.plugin.upload_notifier.healthchecks_notifier import (
    HealthchecksNotifier,
)
from OTCamera.plugin.upload_notifier.payload_factories import (
    HealthchecksS3UploadPayloadFactory,
)
from OTCamera.plugin.upload_notifier.upload_notification_provider import (
    UploadNotificationProvider,
)

PING_URL = "https://hc-ping.com/0a1b2c3d"
TIMEOUT = 3.0


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def notifier(session: MagicMock) -> Iterator[HealthchecksNotifier]:
    config = HealthchecksConfig.model_validate(
        {"ping_url": PING_URL, "timeout": TIMEOUT}
    )
    notifier = HealthchecksNotifier(config, session=session)
    yield notifier
    notifier.close()


def _s3_event() -> S3FileUploaded:
    return S3FileUploaded(
        local_path=Path("/videos/cam_2026-10-06_12-00-00.h264"),
        timestamp=datetime(2026, 10, 6, 12, tzinfo=timezone.utc),
        bucket="videos",
        key="site/cam_2026-10-06_12-00-00.h264",
    )


def test_notify_posts_payload_to_ping_url(
    notifier: HealthchecksNotifier, session: MagicMock
) -> None:
    notifier.notify("hello")
    notifier.close()

    session.post.assert_called_once_with(PING_URL, data=b"hello", timeout=TIMEOUT)


def test_notify_does_not_block_caller(
    notifier: HealthchecksNotifier, session: MagicMock
) -> None:
    release = ThreadEvent()

    def _blocking_post(*args: object, **kwargs: object) -> MagicMock:
        release.wait(5)
        return MagicMock()

    session.post.side_effect = _blocking_post

    notifier.notify("hello")

    assert not release.is_set()
    release.set()
    notifier.close()


@pytest.mark.parametrize("error", [ConnectionError("down"), HTTPError("500")])
def test_failed_ping_is_logged_not_raised(
    notifier: HealthchecksNotifier,
    session: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    session.post.side_effect = error

    with caplog.at_level(logging.WARNING):
        notifier.notify("hello")
        notifier.close()

    assert "Failed to ping healthchecks.io" in caplog.text


def test_http_error_status_is_logged(
    notifier: HealthchecksNotifier,
    session: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session.post.return_value.raise_for_status.side_effect = HTTPError("404")

    with caplog.at_level(logging.WARNING):
        notifier.notify("hello")
        notifier.close()

    assert "Failed to ping healthchecks.io" in caplog.text


def test_unexpected_error_does_not_stop_worker(
    notifier: HealthchecksNotifier, session: MagicMock
) -> None:
    session.post.side_effect = [RuntimeError("boom"), MagicMock()]

    notifier.notify("first")
    notifier.notify("second")
    notifier.close()

    assert session.post.call_count == 2


def test_close_sends_queued_pings_and_stops_worker(
    notifier: HealthchecksNotifier, session: MagicMock
) -> None:
    notifier.notify("first")
    notifier.notify("second")

    notifier.close()

    assert session.post.call_count == 2
    assert not notifier._thread.is_alive()
    session.close.assert_called()


def test_requires_ping_url(session: MagicMock) -> None:
    with pytest.raises(ValueError):
        HealthchecksNotifier(HealthchecksConfig(), session=session)


def test_payload_contains_key_and_bucket() -> None:
    payload = HealthchecksS3UploadPayloadFactory().create(_s3_event())

    assert payload == "Uploaded site/cam_2026-10-06_12-00-00.h264 to bucket videos"


def test_provider_returns_none_without_ping_url() -> None:
    assert UploadNotificationProvider.provide_healthchecks(Config()) is None


def test_provider_returns_notifier_with_ping_url() -> None:
    config = Config.model_validate({"healthchecks": {"ping_url": PING_URL}})

    notifier = UploadNotificationProvider.provide_healthchecks(config)

    assert isinstance(notifier, HealthchecksNotifier)
    notifier.close()


def test_s3_upload_event_triggers_one_ping(
    notifier: HealthchecksNotifier, session: MagicMock
) -> None:
    event_bus = EventBus()
    EventNotificationController(
        event_bus,
        S3FileUploaded,
        notifier,
        payload_factory=HealthchecksS3UploadPayloadFactory(),
    )

    event_bus.enqueue(_s3_event())
    event_bus.process_pending()
    notifier.close()

    session.post.assert_called_once_with(
        PING_URL,
        data=b"Uploaded site/cam_2026-10-06_12-00-00.h264 to bucket videos",
        timeout=TIMEOUT,
    )
