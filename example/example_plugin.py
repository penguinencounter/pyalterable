from pathlib import Path

from alterable.plugins.shared_context import FileContext, ProjectContext


def main(target: Path, ctx: FileContext | ProjectContext):
    print(target, ctx)
