import logging
from pathlib import Path

from OTCamera.netwatch.monitor import (
    HttpNetworkProbe,
    NetworkMonitor,
    NetworkStatusWriter,
)
from OTCamera.netwatch.reconnect import Escalation, ReconnectionWorker


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    writer = NetworkStatusWriter(Path("/tmp/network.json"))

    escalations = [
        Escalation(
            after=15, action=lambda: print("Boy, that escalated with a bit of a delay!")
        ),
        Escalation(after=5, action=lambda: print("Boy, that escalated quickly!")),
    ]
    reconnect_worker = ReconnectionWorker(escalations)

    monitor = NetworkMonitor(
        probe=HttpNetworkProbe(urls=("https://platomo.de",)), wait=5, fail_threshold=2
    )
    monitor.subscribe(writer.write)
    monitor.subscribe(reconnect_worker.process_update)

    reconnect_worker.start()

    monitor.start()
    monitor.join()


if __name__ == "__main__":
    main()
