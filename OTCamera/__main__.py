"""OTCamera application entry point and main loop."""

import logging
import signal
from collections.abc import Callable
from datetime import datetime as dt
from pathlib import Path
from time import sleep
from typing import Any, Protocol

from OTCamera.bsl.board_provider import BoardProvider
from OTCamera.config import Config, parse_user_config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.controller.notification_controller import EventNotificationController
from OTCamera.controller.power_controller import PowerController
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.controller.upload_controller import ThreadedUploadController
from OTCamera.controller.wifi_controller import WifiController
from OTCamera.domain.events import (
    ButtonHeld,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    FileUploaded,
    S3FileUploaded,
    ShutdownRequested,
)
from OTCamera.domain.led import LED
from OTCamera.log import setup_logging
from OTCamera.module.camera.camera_provider import CameraProvider
from OTCamera.plugin.upload.helpers import delete_file
from OTCamera.plugin.upload.upload_provider import UploadProvider
from OTCamera.plugin.upload_notifier.payload_factories import (
    RabbitMQS3UploadToOTCloudPayloadFactory,
)
from OTCamera.plugin.upload_notifier.upload_notification_provider import (
    UploadNotificationProvider,
)

logger = logging.getLogger(__name__)


def _make_button_event_callback(
    event_bus: EventBus,
    event_factory: Callable[[str], Any],
    name: str,
) -> Callable[[], None]:
    """Create a thread-safe button callback that enqueues one event."""

    def _callback() -> None:
        event_bus.enqueue(event_factory(name))

    return _callback


class OTCamera:
    """Main application class orchestrating the recording loop."""

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        camera_controller: CameraController,
        power_controller: PowerController,
        wifi_controller: WifiController,
        schedule_controller: ScheduleController,
        leds: dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._camera = camera_controller
        self._power = power_controller
        self._wifi = wifi_controller
        self._schedule = schedule_controller
        self._leds = leds
        self._shutdown = False
        self._preview_taken = False
        self._power_led_blinked = False

        signal.signal(signal.SIGTERM, self._execute_shutdown)
        signal.signal(signal.SIGINT, self._execute_shutdown)
        event_bus.subscribe(ShutdownRequested, self._on_shutdown_requested)
        Path(config.video.dir).mkdir(parents=True, exist_ok=True)

    def record(self) -> None:
        """Run the main recording loop until all intervals are done or shutdown."""
        logger.info("Starting periodic record")
        self._send_alive_signal()

        try:
            while self._camera.more_intervals and not self._shutdown:
                try:
                    self._loop()
                except OSError as error:
                    if error.errno == 28:
                        logger.exception("No space left on device")
                        self._camera.delete_old_files()
                    else:
                        raise
            if not self._shutdown:
                logger.info("Captured all intervals, stopping")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt, stopping")
        except Exception:
            logger.exception("Unhandled exception in main loop")
            raise
        finally:
            self._execute_shutdown()

    def _loop(self) -> None:
        """Run one iteration of the recording loop."""
        self._event_bus.process_pending()
        self._power.check_power_status()
        self._power.check_pending_shutdown()
        self._wifi.check_pending_wifi_off()
        self._send_alive_signal()

        if self._shutdown:
            return

        if self._schedule.should_record():
            self._camera.start_recording()
            self._camera.split_if_interval_ends()
            self._try_capture_preview()
            return

        self._camera.stop_recording()
        sleep(0.5)

    def _send_alive_signal(self) -> None:
        """Blink the power LED every few seconds to show the app is alive."""
        if self._power.shutdown_active or self._schedule.shutdown_active:
            return

        current_second = dt.now().second
        is_send_time = (current_second % 5) == 3
        power_led = self._leds.get("power")
        if is_send_time and not self._power_led_blinked:
            if power_led is not None:
                blink_count = 2 if self._power.external_power_connected else 1
                power_led.blink(
                    on_time=0.1,
                    off_time=0.1,
                    n=blink_count,
                    background=True,
                )
            self._power_led_blinked = True
        elif not is_send_time and self._power_led_blinked:
            self._power_led_blinked = False

    def _try_capture_preview(self) -> None:
        """Capture a preview at the configured interval when Wi-Fi is on."""
        current_second = dt.now().second
        interval = self._config.preview.interval
        offset = interval - 1
        is_preview_time = (current_second % interval) == offset
        should_capture = (
            is_preview_time
            and self._wifi.wifi_on
            and not self._preview_taken
            and not self._schedule.shutdown_active
        )
        if should_capture:
            self._camera.capture()
            self._preview_taken = True
        elif not is_preview_time and self._preview_taken:
            self._preview_taken = False

    def _on_shutdown_requested(self, event: ShutdownRequested) -> None:
        """Handle a published shutdown request."""
        self._execute_shutdown()

    def _execute_shutdown(self, *args: Any) -> None:
        """Run best-effort shutdown cleanup exactly once."""
        if self._shutdown:
            return
        self._shutdown = True
        logger.info("Stopping OTCamera")

        try:
            self._schedule.set_shutdown_active(True)
        except Exception:
            logger.exception("Failed to set shutdown_active")

        try:
            self._camera.stop_recording()
        except Exception:
            logger.exception("Failed to stop recording")

        logger.info("OTCamera shutdown cleanup finished")


class Closable(Protocol):
    def close(self) -> None: ...


def close_resources(*resources: Closable | None) -> None:
    """ "Try to close all resources, ignoring errors."""
    for resource in resources:
        if resource is None:
            continue
        try:
            resource.close()
        except Exception:
            logger.warning(f"Error closing resource {resource!r}", exc_info=True)


def main(config: Config | None = None, config_file: str = "~/user_config.yaml") -> None:
    """Wire all components and start OTCamera."""
    if config is None:
        config = parse_user_config(config_file)

    setup_logging(config)
    event_bus = EventBus()
    board = BoardProvider.provide(config)

    camera = None
    upload = None
    upload_controller = None
    upload_notification_controller = None
    try:
        camera = CameraProvider.provide(config)

        upload = UploadProvider.provide(config)

        if config.delete_after_upload:
            event_bus.subscribe(FileUploaded, lambda e: delete_file(str(e.local_path)))

        camera_controller = CameraController(camera, config, event_bus, board.leds)
        power_controller = PowerController(
            config,
            event_bus,
            board.leds,
            board.adc,
            board.adc_config,
        )
        wifi_controller = WifiController(config, event_bus, board.leds)
        schedule_controller = ScheduleController(config, event_bus)
        if upload is not None:
            upload_controller = ThreadedUploadController(event_bus, upload)

        notifier = UploadNotificationProvider.provide(config)
        if notifier is not None:
            # Guaranteed by config validation
            assert config.ot_cloud is not None

            # TODO: make this configurable, not hardcoded.
            # Currently supports only upload notifications to OTCloud via RabbitMQ.
            upload_notification_controller = EventNotificationController(
                event_bus,
                S3FileUploaded,
                notifier,
                payload_factory=RabbitMQS3UploadToOTCloudPayloadFactory(
                    config.ot_cloud
                ),
            )

        for name, button in board.buttons.items():
            button.on_pressed(
                _make_button_event_callback(event_bus, ButtonPressed, name)
            )
            button.on_released(
                _make_button_event_callback(event_bus, ButtonReleased, name)
            )
            button.on_held(_make_button_event_callback(event_bus, ButtonHeld, name))

        if "power" in board.buttons and not board.buttons["power"].is_pressed:
            logger.info("Power switch OFF at boot; immediate shutdown")
            power_controller.shutdown(source="boot")
            return

        if power_controller.has_adc and power_controller.is_low_battery:
            logger.warning("Battery low at startup")
            power_controller.shutdown(source="battery")
            return

        if "wifi" in board.buttons:
            wifi_controller.init_from_switch(board.buttons["wifi"].is_pressed)
        if "hour" in board.buttons:
            schedule_controller.init_from_switch(board.buttons["hour"].is_pressed)

        event_bus.process_pending()
        Path(config.video.dir).mkdir(parents=True, exist_ok=True)

        application = OTCamera(
            config=config,
            event_bus=event_bus,
            camera_controller=camera_controller,
            power_controller=power_controller,
            wifi_controller=wifi_controller,
            schedule_controller=schedule_controller,
            leds=board.leds,
        )
        application.record()
    finally:
        close_resources(
            camera, upload, board, upload_controller, upload_notification_controller
        )


if __name__ == "__main__":
    main()
