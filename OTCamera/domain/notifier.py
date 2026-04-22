from abc import ABC, abstractmethod


class Notifier[T](ABC):

    @abstractmethod
    def notify(self, payload: T) -> None:
        raise NotImplementedError
