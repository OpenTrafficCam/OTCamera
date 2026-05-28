import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def delete_file(path: str) -> None:
    """Delete a file after successful upload.

    Args:
        path (str): The file to be deleted.
    """
    try:
        Path(path).unlink()
    except FileNotFoundError as e:
        logger.error("File not found: %s", path)
        raise e
    except Exception as e:
        logger.error("Error deleting file: %s", path)
        raise e

    logger.info("Deleted file %s", path)
