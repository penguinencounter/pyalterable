from pathlib import Path

from alterable import FileContext, ProjectContext


def main(target: Path, ctx: FileContext | ProjectContext):
    print(target, ctx)
