import importlib
from typing import Protocol, cast

from ..plugins.structure import UserPluginSpec, PluginSpec, PreloadPluginSpec


class BuiltinPluginModule(Protocol):
    def about(self) -> PreloadPluginSpec:
        ...


def list_builtins() -> list[PluginSpec]:
    plugins: list[PluginSpec] = []
    for target in [".parse_html"]:
        try:
            module = importlib.import_module(target, __name__)
            try:
                module.about
            except AttributeError:
                raise TypeError(f"Cannot load builtin plugin {target} because it is missing plugin information")
            module_typed: BuiltinPluginModule = cast(BuiltinPluginModule, module)  # smh
            plugin = module_typed.about()
            # Link correctly
            plugin.module = module

        except ImportError:
            pass
    return plugins
