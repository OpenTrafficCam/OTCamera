"""OTCamera application entry point and main loop."""

import logging
import re
import signal
from collections.abc import Callable
from datetime import datetime as dt
from datetime import timedelta
from pathlib import Path
from time import sleep
from typing import Any, Iterator

import psutil

from OTCamera.bsl.board_provider import BoardProvider
from OTCamera.config import Config, parse_user_config
from OTCamera.controller.camera_controller import CameraController
from OTCamera.controller.power_controller import PowerController
from OTCamera.controller.schedule_controller import ScheduleController
from OTCamera.controller.upload_controller import ThreadedUploadController
from OTCamera.controller.wifi_controller import WifiController
from OTCamera.domain.events import (
    ButtonHeld,
    ButtonPressed,
    ButtonReleased,
    EventBus,
    ShutdownRequested,
)
from OTCamera.domain.led import LED
from OTCamera.exceptions import BackendUnavailableError
from OTCamera.html_updater import (
    ConfigDataObject,
    ConfigHtmlId,
    LogDataObject,
    LogHtmlId,
    StatusDataObject,
    StatusHtmlId,
    StatusWebsiteUpdater,
)
from OTCamera.log import setup_logging
from OTCamera.module.camera.camera_provider import CameraProvider
from OTCamera.plugin.upload.upload_provider import UploadProvider

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
        html_updater: StatusWebsiteUpdater,
        leds: dict[str, LED],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._camera = camera_controller
        self._power = power_controller
        self._wifi = wifi_controller
        self._schedule = schedule_controller
        self._html_updater = html_updater
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
        self._update_html()
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
            self._update_html()
            self._preview_taken = True
        elif not is_preview_time and self._preview_taken:
            self._preview_taken = False

    def _update_html(self) -> None:
        """Update the served status page."""
        if self._shutdown:
            return
        self._html_updater.update_info(
            status_info=self._get_status_data(),
            config_info=self._get_config_settings(),
            currently_recording=self._camera.is_recording,
            always_recording=self._schedule.is_24_7_mode,
            external_power_supply_connected=self._power.external_power_connected,
        )

    def _get_status_data(self) -> StatusDataObject:
        """Build the status DTO for the HTML updater."""
        video_dir = Path(self._config.video.dir).expanduser().resolve()
        free_bytes = psutil.disk_usage(str(video_dir)).free
        free_gb = free_bytes / (1024 * 1024 * 1024)
        num_videos = (
            len(
                [
                    path
                    for path in video_dir.iterdir()
                    if path.suffix == f".{self._config.video.format}"
                ]
            )
            if video_dir.is_dir()
            else 0
        )

        time_until_wifi_off = "--:--:--"
        if self._wifi.switch_off_time is not None:
            wifi_delay = timedelta(seconds=self._config.wifi.delay)
            remaining = (self._wifi.switch_off_time + wifi_delay) - dt.now()
            total_seconds = remaining.total_seconds()
            if total_seconds > 0:
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_until_wifi_off = (
                    f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
                )
            else:
                time_until_wifi_off = "00:00:00"

        return StatusDataObject(
            free_diskspace=(StatusHtmlId.FREE_DISKSPACE, f"{free_gb:.2f} GB"),
            num_videos_recorded=(StatusHtmlId.NUM_VIDEOS_RECORDED, num_videos),
            currently_recording=(
                StatusHtmlId.CURRENTLY_RECORDING,
                self._camera.is_recording,
            ),
            low_battery=(StatusHtmlId.LOW_BATTERY, self._power.battery_is_low),
            hour_button_active=(
                StatusHtmlId.HOUR_BUTTON_ACTIVE,
                self._schedule.is_24_7_mode,
            ),
            external_power_supply_connected=(
                StatusHtmlId.EXT_POWER_SUPPLY_CONNECTED,
                self._power.external_power_connected,
            ),
            ms_teams_webhook_enabled=(
                StatusHtmlId.MS_TEAMS_WEBHOOK_ENABLED,
                self._config.msteams.enable,
            ),
            time_until_wifi_off=(StatusHtmlId.TIME_UNTIL_WIFI_OFF, time_until_wifi_off),
        )

    def _get_config_settings(self) -> ConfigDataObject:
        """Build the config DTO for the HTML updater."""
        config = self._config
        return ConfigDataObject(
            debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, config.debug_mode),
            start_hour=(ConfigHtmlId.START_HOUR, config.recording.start_hour),
            end_hour=(ConfigHtmlId.END_HOUR, config.recording.end_hour),
            interval_video_split=(
                ConfigHtmlId.INTERVAL_VIDEO_SPLIT,
                config.recording.interval_length,
            ),
            num_intervals=(ConfigHtmlId.NUM_INTERVALS, config.recording.num_intervals),
            preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, config.preview.interval),
            min_free_space=(
                ConfigHtmlId.MIN_FREE_SPACE,
                config.recording.min_free_space,
            ),
            prefix=(ConfigHtmlId.PREFIX, config.prefix),
            video_dir=(ConfigHtmlId.VIDEO_DIR, config.video.dir),
            preview_path=(ConfigHtmlId.PREVIEW_PATH, config.preview.path),
            template_html_path=(
                ConfigHtmlId.TEMPLATE_HTML_PATH,
                config.template_html_path,
            ),
            index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, config.index_html_path),
            fps=(ConfigHtmlId.FPS, config.camera.fps),
            resolution=(ConfigHtmlId.RESOLUTION, config.camera.resolution),
            exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, config.camera.exposure_mode),
            drc_strength=(ConfigHtmlId.DRC_STRENGTH, config.camera.drc_strength),
            rotation=(ConfigHtmlId.ROTATION, config.camera.rotation),
            awb_mode=(ConfigHtmlId.AWB_MODE, config.camera.awb_mode),
            video_format=(ConfigHtmlId.VIDEO_FORMAT, config.video.format),
            preview_format=(ConfigHtmlId.PREVIEW_FORMAT, config.preview.format),
            res_of_saved_video_file=(
                ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE,
                config.video.resolution,
            ),
            h264_profile=(ConfigHtmlId.H264_PROFILE, config.video.encoder.profile),
            h264_level=(ConfigHtmlId.H264_LEVEL, config.video.encoder.level),
            h264_bitrate=(ConfigHtmlId.H264_BITRATE, config.video.encoder.bitrate),
            h264_quality=(ConfigHtmlId.H264_QUALITY, config.video.encoder.quality),
            use_led=(ConfigHtmlId.USE_LED, config.hardware.use_leds),
            use_buttons=(ConfigHtmlId.USE_BUTTONS, config.hardware.use_buttons),
            wifi_delay=(ConfigHtmlId.WIFI_DELAY, config.wifi.delay),
        )

    def _get_log_info(self, start_idx: int, num: int) -> LogDataObject:
        """Build the log DTO for the offline page."""
        log_dir = Path(self._config.video.dir).expanduser().resolve()
        if not log_dir.is_dir():
            return LogDataObject(log_data=(LogHtmlId.LOG_DATA, ""))

        sorted_logs = _get_log_files_sorted(log_dir.iterdir())
        recent_logs = sorted_logs[start_idx : start_idx + num]
        recent_logs.reverse()
        log_data = ""
        for log_file_path in recent_logs:
            log_data += f"File: {log_file_path}\n"
            with open(log_file_path, "r", encoding="utf-8") as file_handle:
                log_data += file_handle.read() + "\n"
        return LogDataObject(log_data=(LogHtmlId.LOG_DATA, log_data))

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

        try:
            self._html_updater.display_offline_info(
                self._get_log_info(0, self._config.num_log_files_html),
            )
        except Exception:
            logger.exception("Failed to display offline info")

        logger.info("OTCamera shutdown cleanup finished")


def _get_log_files_sorted(log_files: Iterator[Path]) -> list[Path]:
    """Return log files sorted by timestamp encoded in the filename."""
    regex = r"_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})"
    with_timestamp: list[tuple[dt, Path]] = []
    without_timestamp: list[Path] = []
    for log_file in log_files:
        if log_file.suffix != ".log":
            continue
        match = re.search(regex, log_file.stem)
        if match:
            timestamp = dt.strptime(match.group(1), "%Y-%m-%d_%H-%M-%S")
            with_timestamp.append((timestamp, log_file))
        else:
            without_timestamp.append(log_file)
    with_timestamp.sort(key=lambda entry: entry[0], reverse=True)
    return [log_file for _, log_file in with_timestamp] + without_timestamp


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
    try:
        camera = CameraProvider.provide(config)

        try:
            upload = UploadProvider.provide(config)
        except BackendUnavailableError:
            logger.error(
                "Upload backend is configured, but not available for uploading."
            )
            raise

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
        upload_controller = ThreadedUploadController(event_bus, upload)

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

        html_updater = StatusWebsiteUpdater(
            template_html_path=config.template_html_path,
            offline_html_path=config.offline_html_path,
            html_save_path=config.index_html_path,
            debug_mode_on=config.debug_mode,
        )

        event_bus.process_pending()
        Path(config.video.dir).mkdir(parents=True, exist_ok=True)

        application = OTCamera(
            config=config,
            event_bus=event_bus,
            camera_controller=camera_controller,
            power_controller=power_controller,
            wifi_controller=wifi_controller,
            schedule_controller=schedule_controller,
            html_updater=html_updater,
            leds=board.leds,
        )
        application.record()
    finally:
        for resource in [camera, upload, upload_controller]:
            if resource is None:
                continue
            try:
                resource.close()
            except Exception:
                logger.debug("Error closing resource", exc_info=True)
        board.close()


if __name__ == "__main__":
    main()
