import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException

from OTCamera.netwatch.monitor import NetworkMonitor, NetworkStatus, StatusUpdate
from OTCamera.netwatch.probe import HttpNetworkProbe
from OTCamera.netwatch.writer import NetworkStatusWriter


class _Break(Exception):
    """Breaks out of NetworkMonitor.run() after a controlled number of probe calls."""


def _run_monitor(monitor: NetworkMonitor) -> None:
    with patch("OTCamera.netwatch.monitor.sleep"):
        with pytest.raises(_Break):
            monitor.run()


def _make_monitor(
    probe: MagicMock | None = None,
    success_threshold: int = 3,
    fail_threshold: int = 5,
) -> NetworkMonitor:
    if probe is None:
        probe = MagicMock()
    return NetworkMonitor(
        probe=probe,
        wait=1,
        success_threshold=success_threshold,
        fail_threshold=fail_threshold,
    )


class TestHttpNetworkProbe:
    def test_requires_at_least_one_url(self) -> None:
        with pytest.raises(ValueError):
            HttpNetworkProbe(urls=[], timeout=None)

    def test_returns_true_on_successful_request(self) -> None:
        probe = HttpNetworkProbe(urls=["http://example.com"], timeout=None)
        with patch("OTCamera.netwatch.probe.requests.head") as mock_head:
            mock_head.return_value = MagicMock(status_code=200)
            assert probe.is_online() is True

    def test_returns_false_when_all_urls_fail(self) -> None:
        probe = HttpNetworkProbe(urls=["http://a.com", "http://b.com"], timeout=None)
        with patch("OTCamera.netwatch.probe.requests.head") as mock_head:
            mock_head.side_effect = RequestException("network error")
            assert probe.is_online() is False

    def test_falls_back_to_next_url_on_failure(self) -> None:
        probe = HttpNetworkProbe(
            urls=["http://fail.com", "http://ok.com"], timeout=None
        )
        with patch("OTCamera.netwatch.probe.requests.head") as mock_head:
            mock_head.side_effect = [
                RequestException("fail"),
                MagicMock(status_code=200),
            ]
            assert probe.is_online() is True
            assert mock_head.call_count == 2

    def test_does_not_try_further_urls_after_first_success(self) -> None:
        probe = HttpNetworkProbe(
            urls=["http://first.com", "http://second.com"], timeout=None
        )
        with patch("OTCamera.netwatch.probe.requests.head") as mock_head:
            mock_head.return_value = MagicMock(status_code=200)
            probe.is_online()
            assert mock_head.call_count == 1


class TestNetworkStatusWriter:
    def test_creates_json_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "network.json"
        writer = NetworkStatusWriter(out_file)
        update = StatusUpdate(status=NetworkStatus.ONLINE, last_changed_at=1234567890.0)

        writer.write(update)

        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["status"] == "ONLINE"
        assert data["changed"] == 1234567890.0

    def test_uses_enum_name_as_status_string(self, tmp_path: Path) -> None:
        out_file = tmp_path / "network.json"
        writer = NetworkStatusWriter(out_file)

        for status in (
            NetworkStatus.ONLINE,
            NetworkStatus.OFFLINE,
            NetworkStatus.UNKNOWN,
        ):
            writer.write(StatusUpdate(status=status, last_changed_at=0.0))
            data = json.loads(out_file.read_text())
            assert data["status"] == status.name

    def test_overwrites_previous_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "network.json"
        writer = NetworkStatusWriter(out_file)

        writer.write(StatusUpdate(status=NetworkStatus.ONLINE, last_changed_at=1.0))
        writer.write(StatusUpdate(status=NetworkStatus.OFFLINE, last_changed_at=2.0))

        data = json.loads(out_file.read_text())
        assert data["status"] == "OFFLINE"
        assert data["changed"] == 2.0


class TestNetworkMonitorInitialState:
    def test_status_is_unknown(self) -> None:
        assert _make_monitor().status == NetworkStatus.UNKNOWN

    def test_subscribe_registers_callable(self) -> None:
        monitor = _make_monitor()
        callback = MagicMock()
        monitor.subscribe(callback)
        assert callback in monitor.subscribers


class TestNetworkMonitorTransitions:
    def test_transitions_to_online_after_success_threshold(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.ONLINE

    def test_does_not_transition_below_success_threshold(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.UNKNOWN

    def test_transitions_to_offline_after_fail_threshold(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [False] * 5 + [_Break()]
        monitor = _make_monitor(probe=probe, fail_threshold=5)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.OFFLINE

    def test_does_not_transition_below_fail_threshold(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [False] * 4 + [_Break()]
        monitor = _make_monitor(probe=probe, fail_threshold=5)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.UNKNOWN

    def test_transitions_online_to_offline(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True] * 3 + [False] * 5 + [_Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3, fail_threshold=5)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.OFFLINE

    def test_transitions_offline_to_online(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [False] * 5 + [True] * 3 + [_Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3, fail_threshold=5)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.ONLINE


class TestNetworkMonitorStreaks:
    def test_resets_fail_streak_on_success(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [False, False, True, _Break()]
        monitor = _make_monitor(probe=probe)

        _run_monitor(monitor)

        assert monitor._fail_streak == 0

    def test_resets_success_streak_on_failure(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, False, _Break()]
        monitor = _make_monitor(probe=probe)

        _run_monitor(monitor)

        assert monitor._success_streak == 0

    def test_interrupted_streak_does_not_trigger_transition(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, False, True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)

        _run_monitor(monitor)

        assert monitor.status == NetworkStatus.UNKNOWN


class TestNetworkMonitorSubscribers:
    def test_notifies_subscriber_on_status_change(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)
        subscriber = MagicMock()
        monitor.subscribe(subscriber)

        _run_monitor(monitor)

        subscriber.assert_called_once()
        (update,) = subscriber.call_args.args
        assert update.status == NetworkStatus.ONLINE

    def test_does_not_notify_subscriber_without_status_change(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)
        subscriber = MagicMock()
        monitor.subscribe(subscriber)

        _run_monitor(monitor)

        subscriber.assert_not_called()

    def test_notifies_subscriber_only_once_per_transition(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, True, True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)
        subscriber = MagicMock()
        monitor.subscribe(subscriber)

        _run_monitor(monitor)

        subscriber.assert_called_once()

    def test_notifies_all_subscribers(self) -> None:
        probe = MagicMock()
        probe.is_online.side_effect = [True, True, True, _Break()]
        monitor = _make_monitor(probe=probe, success_threshold=3)
        sub_a, sub_b = MagicMock(), MagicMock()
        monitor.subscribe(sub_a)
        monitor.subscribe(sub_b)

        _run_monitor(monitor)

        sub_a.assert_called_once()
        sub_b.assert_called_once()
