from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Self, TypeVar


class BaseProps:
    """
    Generic data storage. Used directly in ProjectContext.
    Extend this class to define dependencies.
    """

    def __init__(self):
        self._auto_props: dict[str, Callable[[Self], Any]] = {}

    def __getattribute__(self, item: str):
        default = super().__getattribute__
        PASSTHROUGH = ["new_property"]
        if item not in PASSTHROUGH and item in default("_auto_props"):
            return self._auto_props[item](self)
        return default(item)

    def __setattr__(self, key: str, value: Any):
        default = super().__setattr__
        PASSTHROUGH = ["_auto_props"]
        if key in PASSTHROUGH:
            return default(key, value)
        PROTECTED = ["new_property", "__getattribute__", "__setattr__"]
        if key in PROTECTED:
            raise KeyError(f"writing to {key} is not permitted")
        if key in self._auto_props:
            raise KeyError(f"{key} is a read only property")
        return default(key, value)

    def __delattr__(self, item: str):
        default = super().__delattr__
        if item in self._auto_props:
            del self._auto_props[item]
            del self.__dict__[item]
            return
        return default(item)

    def new_property(self, target: str, provider: Callable[[Self], Any]):
        self.__dict__[target] = None
        self._auto_props[target] = provider


class BaseFileProps(BaseProps):
    """
    Generic data storage. Used directly in FileContext.
    Provides basic file information.
    """

    def __init__(self, fullpath: Path):
        super().__init__()
        self.fullpath = fullpath
        self.name = self.fullpath.name
        self.new_property("exists", lambda _: self.fullpath.exists())

        def read_bytes() -> bytes:
            with open(self.fullpath, "rb") as f:
                return f.read()

        self.new_property("raw", lambda _: read_bytes())
        self.new_property("content", lambda _: read_bytes().decode("utf-8"))


ddK = TypeVar("ddK")
ddV = TypeVar("ddV")


class CtxDefaultDict(dict[ddK, ddV]):
    def __init__(self, provider: Callable[[str], ddV], **kwargs):
        super().__init__(**kwargs)
        self.provider = provider

    def __missing__(self, key: str):
        self[key] = value = self.provider(key)
        return value


class FileContext:
    def __init__(self, path: Path):
        self.data = BaseFileProps(path)


class ProjectContext:
    def __init__(self):
        self.data = BaseProps()
        self.files: CtxDefaultDict[str, FileContext] = CtxDefaultDict(
            lambda k: FileContext(Path(k).absolute())
        )
