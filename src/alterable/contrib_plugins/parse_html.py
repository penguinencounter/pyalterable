from pathlib import Path

from bs4 import BeautifulSoup

from ..plugins.shared_context import BaseFileProps, FileContext
from ..plugins.structure import FilePluginPipelineInfo, PreloadPluginSpec


def about() -> PreloadPluginSpec:
    return PreloadPluginSpec(
        name="builtin/parse_html",
        pipeline=FilePluginPipelineInfo("main", [r".*\.html$"]),
        provides={"parse_html", "builtin/parse_html"},
        use=[],
        module=None,  # Will be filled by caller
    )


def main(target: Path, context: FileContext):
    def lazy_parse(self_: BaseFileProps):
        return BeautifulSoup(self_.content, "html.parser")

    context.data.new_property("html", lazy_parse)
