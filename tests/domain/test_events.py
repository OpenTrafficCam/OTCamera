import threading

from OTCamera.domain.events import (
    BatteryLow,
    ButtonPressed,
    EventBus,
    RecordingStarted,
    ShutdownRequested,
    WifiOff,
    WifiOn,
)


class TestPublish:
    def test_publish_dispatches_immediately(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        event = RecordingStarted(filename="/tmp/video.h264")
        bus.subscribe(RecordingStarted, received.append)

        bus.publish(event)

        assert received == [event]

    def test_publish_no_cross_talk(self) -> None:
        bus = EventBus()
        received: list[WifiOn] = []
        bus.subscribe(WifiOn, received.append)

        bus.publish(WifiOff())

        assert received == []

    def test_publish_exception_does_not_propagate(self) -> None:
        bus = EventBus()
        received: list[BatteryLow] = []

        def broken_callback(event: BatteryLow) -> None:
            raise RuntimeError("boom")

        bus.subscribe(BatteryLow, broken_callback)
        bus.subscribe(BatteryLow, received.append)

        bus.publish(BatteryLow())

        assert len(received) == 1


class TestEnqueue:
    def test_enqueue_does_not_dispatch_immediately(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        event = RecordingStarted(filename="/tmp/video.h264")
        bus.subscribe(RecordingStarted, received.append)

        bus.enqueue(event)

        assert received == []

    def test_process_pending_dispatches_queued_events(self) -> None:
        bus = EventBus()
        received: list[RecordingStarted] = []
        event = RecordingStarted(filename="/tmp/video.h264")
        bus.subscribe(RecordingStarted, received.append)

        bus.enqueue(event)
        bus.process_pending()

        assert received == [event]

    def test_enqueue_is_thread_safe(self) -> None:
        bus = EventBus()
        received: list[ButtonPressed] = []
        bus.subscribe(ButtonPressed, received.append)

        def enqueue_from_thread() -> None:
            bus.enqueue(ButtonPressed(name="power"))

        thread = threading.Thread(target=enqueue_from_thread)
        thread.start()
        thread.join()

        bus.process_pending()

        assert len(received) == 1
        assert received[0].name == "power"


class TestSubscriptionManagement:
    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[BatteryLow] = []
        bus.subscribe(BatteryLow, received.append)

        bus.unsubscribe(BatteryLow, received.append)
        bus.publish(BatteryLow())

        assert received == []

    def test_clear(self) -> None:
        bus = EventBus()
        received: list[BatteryLow] = []
        bus.subscribe(BatteryLow, received.append)
        bus.enqueue(BatteryLow())

        bus.clear()
        bus.publish(BatteryLow())
        bus.process_pending()

        assert received == []


def test_shutdown_requested_field() -> None:
    assert ShutdownRequested(source="battery").source == "battery"
