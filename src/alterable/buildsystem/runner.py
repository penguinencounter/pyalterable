import logging
from pathlib import Path

from ..plugins.prepare import prepare
from ..plugins.shared_context import ProjectContext
from ..plugins.structure import PluginSpec
from .resolves import DepLoadStruct

log = logging.getLogger("runner")


def run_steps(
    sandbox: Path, actions: list[DepLoadStruct], plugins: dict[str, PluginSpec]
):
    ctx = ProjectContext()
    for item in actions:
        source = plugins[item.name]
        try:
            bindings = prepare(source, sandbox, ctx)
            for run in bindings:
                run()
        except Exception as e:
            log.critical(
                f"While preparing [bright_blue]{source.name}[/]: "
                f"[red][bold]{type(e).__name__}[/]: [italic]{e}[/][/]",
                extra={"markup": True},
            )
            raise RuntimeError(f"An error occured while preparing {source}")
