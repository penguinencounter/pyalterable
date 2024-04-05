from ..plugins.structure import (
    PreloadPluginSpec,
    FilePluginPipelineInfo,
)


def about() -> PreloadPluginSpec:
    return PreloadPluginSpec(
        name="builtin/parse_html",
        pipeline=FilePluginPipelineInfo("main", [r".*\.html$"]),
        provides={"parse_html", "builtin/parse_html"},
        use=[],
        module=None,  # Will be filled by caller
    )


def main():
    pass
