"""Logging setup for OTCamera."""

import json
import logging
from datetime import datetime as dt
from pathlib import Path

import requests

from OTCamera.config import Config


class MsTeamsHandler(logging.Handler):
    """Logging handler that posts log messages to an MS Teams webhook."""

    def __init__(self, webhook_url: str, max_failures: int = 2) -> None:
        super().__init__()
        self._webhook_url = webhook_url
        self._max_failures = max_failures
        self._failed_attempts = 0
        self._disabled = False

    def emit(self, record: logging.LogRecord) -> None:
        """Send one formatted log record to MS Teams."""
        if self._disabled or record.levelno <= logging.DEBUG:
            return

        message = self.format(record)
        try:
            response = requests.post(
                self._webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps({"text": message}),
                timeout=10,
            )
        except requests.exceptions.RequestException:
            self._failed_attempts += 1
        else:
            if 400 <= response.status_code < 600:
                self._failed_attempts += 1
            else:
                self._failed_attempts = 0

        if self._failed_attempts >= self._max_failures:
            self._disabled = True


def setup_logging(config: Config) -> None:
    """Configure root logging handlers from config."""
    log_path = _log_file_path(config)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if config.debug_mode else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    # reduce pika noise - only report warnings or higher
    logging.getLogger("pika").setLevel(logging.WARNING)

    file_handler = logging.FileHandler(str(log_path), mode="a")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if config.msteams.enable and config.msteams.url:
        teams_handler = MsTeamsHandler(
            webhook_url=config.msteams.url,
            max_failures=config.msteams.max_failed_send_attempts,
        )
        teams_handler.setFormatter(formatter)
        root_logger.addHandler(teams_handler)


def _log_file_path(config: Config) -> Path:
    """Return the logfile path derived from config."""
    timestamp = dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = (
        Path(config.video.dir)
        / f"{config.prefix}_FR{config.camera.fps}_{timestamp}.log"
    )
    return filename.expanduser().resolve()
