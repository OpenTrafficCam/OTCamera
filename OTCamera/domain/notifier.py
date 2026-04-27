from abc import ABC, abstractmethod


class Notifier[T](ABC):
    """Abstract interface for sending a typed payload to an external system."""

    @abstractmethod
    def notify(self, payload: T) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release underlying resources."""
        raise NotImplementedError
