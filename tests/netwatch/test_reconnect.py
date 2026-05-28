from unittest.mock import MagicMock, patch

import pytest

from OTCamera.netwatch.monitor import NetworkStatus, StatusUpdate
from OTCamera.netwatch.reconnect import Escalation, ReconnectionWorker


class _StopLoop(Exception):
    """Breaks out of ReconnectionWorker.run() after a controlled number of cycles."""


class TestEscalation:
    def test_sorted_by_after_ascending(self) -> None:
        e1 = Escalation(after=10, action=MagicMock())
        e2 = Escalation(after=5, action=MagicMock())
        e3 = Escalation(after=20, action=MagicMock())

        worker = ReconnectionWorker(escalations=[e1, e2, e3])

        assert worker.escalations == [e2, e1, e3]


class TestReconnectionWorkerInit:
    def test_requires_at_least_one_escalation(self) -> None:
        with pytest.raises(ValueError):
            ReconnectionWorker(escalations=[])

    def test_initial_stage_is_first_sorted_escalation(self) -> None:
        e_slow = Escalation(after=30, action=MagicMock())
        e_fast = Escalation(after=5, action=MagicMock())

        worker = ReconnectionWorker(escalations=[e_slow, e_fast])

        assert worker.current_stage == e_fast


class TestReconnectionWorkerProcessUpdate:
    def test_tracks_offline_status(self) -> None:
        worker = ReconnectionWorker(
            escalations=[Escalation(after=10, action=MagicMock())]
        )

        worker.process_update(
            StatusUpdate(status=NetworkStatus.OFFLINE, last_changed_at=1.0)
        )

        assert worker._status == NetworkStatus.OFFLINE

    def test_tracks_online_status(self) -> None:
        worker = ReconnectionWorker(
            escalations=[Escalation(after=10, action=MagicMock())]
        )
        worker._status = NetworkStatus.OFFLINE

        worker.process_update(
            StatusUpdate(status=NetworkStatus.ONLINE, last_changed_at=2.0)
        )

        assert worker._status == NetworkStatus.ONLINE

    def test_resets_escalation_stage_when_coming_online(self) -> None:
        e1 = Escalation(after=5, action=MagicMock())
        e2 = Escalation(after=10, action=MagicMock())
        worker = ReconnectionWorker(escalations=[e1, e2])

        worker._advance_stage()
        assert worker.current_stage == e2

        worker._status = NetworkStatus.OFFLINE
        worker.process_update(
            StatusUpdate(status=NetworkStatus.ONLINE, last_changed_at=3.0)
        )

        assert worker.current_stage == e1


class TestReconnectionWorkerRun:
    def test_triggers_action_when_offline_long_enough(self) -> None:
        action = MagicMock()
        worker = ReconnectionWorker(
            escalations=[Escalation(after=5, action=action)], cycle=False
        )
        worker._status = NetworkStatus.OFFLINE
        worker._last_changed_at = 0

        with (
            patch("OTCamera.netwatch.reconnect.monotonic", return_value=10),
            patch("OTCamera.netwatch.reconnect.sleep"),
        ):
            worker.run()

        action.assert_called_once()

    def test_does_not_trigger_action_before_delay(self) -> None:
        action = MagicMock()
        worker = ReconnectionWorker(
            escalations=[Escalation(after=30, action=action)], cycle=False
        )
        worker._status = NetworkStatus.OFFLINE
        worker._last_changed_at = 0

        call_count = [0]

        def fake_sleep(_: float) -> None:
            call_count[0] += 1
            if call_count[0] >= 3:
                raise _StopLoop()

        with (
            patch("OTCamera.netwatch.reconnect.monotonic", return_value=10),
            patch("OTCamera.netwatch.reconnect.sleep", side_effect=fake_sleep),
        ):
            with pytest.raises(_StopLoop):
                worker.run()

        action.assert_not_called()

    def test_does_not_trigger_action_while_online(self) -> None:
        action = MagicMock()
        worker = ReconnectionWorker(
            escalations=[Escalation(after=5, action=action)], cycle=False
        )
        worker._status = NetworkStatus.ONLINE
        worker._last_changed_at = 0

        call_count = [0]

        def fake_sleep(_: float) -> None:
            call_count[0] += 1
            if call_count[0] >= 3:
                raise _StopLoop()

        with (
            patch("OTCamera.netwatch.reconnect.monotonic", return_value=10),
            patch("OTCamera.netwatch.reconnect.sleep", side_effect=fake_sleep),
        ):
            with pytest.raises(_StopLoop):
                worker.run()

        action.assert_not_called()

    def test_exits_after_all_escalations_exhausted_without_cycle(self) -> None:
        actions = [MagicMock(), MagicMock()]
        worker = ReconnectionWorker(
            escalations=[
                Escalation(after=5, action=actions[0]),
                Escalation(after=10, action=actions[1]),
            ],
            cycle=False,
        )
        worker._status = NetworkStatus.OFFLINE
        worker._last_changed_at = 0

        with (
            patch("OTCamera.netwatch.reconnect.monotonic", return_value=20),
            patch("OTCamera.netwatch.reconnect.sleep"),
        ):
            worker.run()

        actions[0].assert_called_once()
        actions[1].assert_called_once()
        assert worker.current_stage is None

    def test_cycles_through_escalations_when_cycle_is_true(self) -> None:
        call_count = [0]

        def counting_action() -> None:
            call_count[0] += 1
            if call_count[0] >= 3:
                raise _StopLoop()

        worker = ReconnectionWorker(
            escalations=[Escalation(after=5, action=counting_action)],
            cycle=True,
        )
        worker._status = NetworkStatus.OFFLINE
        worker._last_changed_at = 0

        with (
            patch("OTCamera.netwatch.reconnect.monotonic", return_value=10),
            patch("OTCamera.netwatch.reconnect.sleep"),
        ):
            with pytest.raises(_StopLoop):
                worker.run()

        assert call_count[0] == 3
