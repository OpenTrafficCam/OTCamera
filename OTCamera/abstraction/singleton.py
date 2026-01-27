from typing import Any, Optional, Type, TypeVar

T = TypeVar("T", bound="Singleton")


class Singleton(object):
    """Implements the Singleton design pattern.

    Classes inheriting from `Singleton` become a singleton class.
    Meaning only one instance is created.
    Constructing another instance of the concrete class inheriting from `Singleton`
    will return the first instance.
    """

    __it__: Optional["Singleton"] = None

    def __new__(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwargs)
        return it

    def init(self, *args: Any, **kwargs: Any) -> None:
        pass
