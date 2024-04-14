import logging
from pathlib import Path

from alterable.plugins.shared_context import FileContext
from alterable.plugins.structure import PreloadPluginSpec, FilePluginPipelineInfo

log = logging.getLogger("file_ctx_dbg")


def about() -> PreloadPluginSpec:
    return PreloadPluginSpec(
        name="builtin/file_ctx_dbg",
        pipeline=FilePluginPipelineInfo("main", [r""]),
        provides={"file_ctx_dbg", "builtin/file_ctx_dbg"},
        use=[],
        module=None,  # Will be filled by caller
    )


def main(target: Path, context: FileContext):
    builder = f"File context for [bold bright_blue]{target.name}[/]:\n"
    for prop in dir(context.data):
        if prop.startswith("__"):
            continue
        try:
            value = getattr(context.data, prop)
            builder += f"  [bright_green]{prop}[/] => {type(value).__name__}"
        except AttributeError:
            builder += f"  [red]{prop}[/] [bold bright_red]phantom??[/]"
        except Exception as e:
            builder += f"  [red]{prop}[/] [red]!! [bold]{type(e).__name__}[/] {str(e)[:120]}[/]"
        builder += "\n"
    log.info(builder[:-1], extra={"markup": True})
