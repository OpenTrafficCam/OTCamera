import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Sequence

from OTCamera.netwatch.monitor import NetworkStatus, StatusUpdate

logger = logging.getLogger(__name__)


@dataclass(eq=True, order=True, frozen=True)
class Escalation:
    """One escalation step to re-establish a network connection."""

    # Seconds after which the escalation is triggered.
    after: int
    # The callable to execute when this stage is triggered.
    action: Callable = field(compare=False)


class ReconnectionWorker(Thread):
    """Executes escalation steps to attempt to re-establish a network connection."""

    def __init__(self, escalations: Sequence[Escalation], cycle: bool = True):

        if len(escalations) < 1:
            raise ValueError("Must have at least one escalation to trigger.")

        super().__init__(daemon=True)

        self.cycle = cycle
        self.escalations = sorted(escalations)

        self.escalations_iter: Iterator[Escalation]
        self.current_stage: Escalation | None = None
        self._reset_escalation_stage()

        self._lock = Lock()

        self._status = NetworkStatus.UNKNOWN
        self._last_changed_at = monotonic()

    def _advance_stage(self) -> None:
        try:
            self.current_stage = next(self.escalations_iter)
        except StopIteration:
            if self.cycle:
                self.escalations_iter = iter(self.escalations)
                self.current_stage = next(self.escalations_iter)
            else:
                self.current_stage = None

    def _reset_escalation_stage(self) -> None:
        self.escalations_iter = iter(self.escalations)
        self.current_stage = next(self.escalations_iter)

    def process_update(self, status_update: StatusUpdate) -> None:
        """Process an update of the network status.

        Update attributes keeping track of the status and for how long we have been in
        that status.

        Should subscribe to process continuously updating the current network status
        via StatusUpdate objects.

        Args:
             status_update: The StatusUpdate that is processed.
        """

        logger.debug("EscalationWorker received status update.")

        with self._lock:
            if (
                self._status != NetworkStatus.ONLINE
                and status_update.status == NetworkStatus.ONLINE
            ):
                self._reset_escalation_stage()

            if self._status != status_update.status:
                self._last_changed_at = monotonic()
            self._status = status_update.status

    def run(self) -> None:
        while True:
            action_to_run = None
            with self._lock:
                if self.current_stage is None:
                    break
                if self._status == NetworkStatus.OFFLINE:
                    time_since = monotonic() - self._last_changed_at
                    logger.debug("We have been offline since %d seconds.", time_since)
                    if time_since >= self.current_stage.after:
                        action_to_run = self.current_stage.action
                        self._advance_stage()

            if action_to_run is not None:
                action_to_run()

            sleep(1)

        logger.warning("All escalation options exhausted. Will stop operation.")
