"""Provides a class for persisting the network status to a a file.

This is inteded to be a form of very basic IPC. Status can be read
by other processed to make decisions based on the current network status.
"""

import json
import logging
from pathlib import Path

from OTCamera.netwatch.monitor import StatusUpdate

logger = logging.getLogger(__name__)


class NetworkStatusWriter:
    """Writes the network status to a file.

    The `write()` method can be used as a subscriber to
    NetworkMonitor status updates.
    """

    def __init__(self, out_file: Path):
        """Create new `NetworkStatusWriter`."""
        self.out_file = out_file

    def write(self, update: StatusUpdate) -> None:
        """Persist a network connection StatusUpdate.

        Args:
            update: The StatusUpdate instance to write to a file.
        """
        payload = {"status": update.status.name, "changed": update.last_changed_at}
        with open(self.out_file, "w") as f:
            json.dump(payload, f)

        logger.debug("Wrote network status to %s", self.out_file)
