"""Logging setup for OTCamera."""

import logging
from datetime import datetime as dt
from pathlib import Path

from OTCamera.config import Config


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


def _log_file_path(config: Config) -> Path:
    """Return the logfile path derived from config."""
    timestamp = dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = (
        Path(config.video.dir)
        / f"{config.prefix}_FR{config.camera.fps}_{timestamp}.log"
    )
    return filename.expanduser().resolve()
