from pathlib import Path

from bs4 import BeautifulSoup

from alterable.plugins.shared_context import FileContext


def main(target: Path, ctx: FileContext):
    try:
        htm: BeautifulSoup = ctx.data.html
        print(target, len(list(htm.descendants)), "desc")
    except AttributeError:
        print(f"can't access html on {ctx.data.fullpath}")
