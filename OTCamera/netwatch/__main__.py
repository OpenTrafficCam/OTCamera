"""Script for starting a continuously running network monitoring service."""

import argparse
import logging
from pathlib import Path

from OTCamera.netwatch.monitor import NetworkMonitor
from OTCamera.netwatch.probe import HttpNetworkProbe
from OTCamera.netwatch.writer import NetworkStatusWriter


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor network connectivity and write status to a file."
    )
    parser.add_argument(
        "--urls",
        nargs="+",
        required=True,
        metavar="URL",
        help="One or more URLs to probe sequentially in the provided order.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--wait",
        type=int,
        required=True,
        metavar="SECONDS",
        help="Seconds to wait between probes.",
    )
    parser.add_argument(
        "--success-threshold",
        type=int,
        default=3,
        metavar="N",
        help="Consecutive successes before ONLINE (default: 3).",
    )
    parser.add_argument(
        "--fail-threshold",
        type=int,
        default=5,
        metavar="N",
        help="Consecutive failures before OFFLINE (default: 5).",
    )
    parser.add_argument(
        "--out-file",
        type=Path,
        required=True,
        metavar="PATH",
        help="File path for the JSON status output.",
    )
    return parser.parse_args()


def main() -> None:
    """Pass command line arguments and start the monitoring thread."""
    args = _parse_args()
    logging.basicConfig(level=logging.DEBUG)

    writer = NetworkStatusWriter(args.out_file)

    monitor = NetworkMonitor(
        probe=HttpNetworkProbe(urls=args.urls, timeout=args.timeout),
        wait=args.wait,
        success_threshold=args.success_threshold,
        fail_threshold=args.fail_threshold,
    )
    monitor.subscribe(writer.write)
    monitor.start()
    monitor.join()


if __name__ == "__main__":
    main()
