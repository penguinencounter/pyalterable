import importlib
import logging
from typing import Protocol, cast

from ..plugins.structure import PluginSpec, PreloadPluginSpec, UserPluginSpec

log = logging.getLogger("plugin builtins")
PLUGIN_LIST = [".parse_html", ".file_context_debugger"]


class BuiltinPluginModule(Protocol):
    def about(self) -> PreloadPluginSpec: ...


def list_builtins() -> list[PluginSpec]:
    plugins: list[PluginSpec] = []
    for target in PLUGIN_LIST:
        try:
            log.debug(
                f"Constructing [bright_blue]{target}[/] by loading its source file",
                extra={"markup": True},
            )
            module = importlib.import_module(target, __name__)
            try:
                module.about
            except AttributeError:
                raise TypeError(
                    f"Cannot load builtin plugin {target} because it is missing plugin information"
                )
            module_typed: BuiltinPluginModule = cast(BuiltinPluginModule, module)  # smh
            plugin = module_typed.about()
            # Link correctly
            plugin.module = module
            plugins.append(plugin)
        except ImportError as e:
            log.debug(
                f"load of [bright_blue]{target}[/] [yellow][bold]failed[/] because of an import error:[/] [italic]{e}[/]",
                extra={"markup": True},
            )
        except Exception as e:
            log.error(
                f"load of [bright_blue]{target}[/] [bold red]failed[/] "
                f"because of [red][bold]{type(e).__name__}[/]: [italic]{e}[/][/]",
                extra={"markup": True},
            )
    log.info(
        f"{len(plugins)} builtin plugins - {', '.join(map(lambda x: x.name, plugins[:8]))}"
    )
    return plugins
