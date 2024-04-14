import logging
from pathlib import Path

from .resolves import DepLoadStruct
from ..plugins.prepare import prepare
from ..plugins.structure import PluginSpec

log = logging.getLogger("runner")


def run_steps(
    sandbox: Path, actions: list[DepLoadStruct], plugins: dict[str, PluginSpec]
):
    for item in actions:
        source = plugins[item.name]
        try:
            bindings = prepare(source, sandbox)
            for bind in bindings:
                bind(None)
        except Exception as e:
            log.critical(
                f"While preparing [bright_blue]{source.name}[/]: "
                f"[red][bold]{type(e).__name__}[/]: [italic]{e}[/][/]",
                extra={"markup": True},
            )
            raise RuntimeError(f"An error occured while preparing {source}")
