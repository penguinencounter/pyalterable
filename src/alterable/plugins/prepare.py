"""
The "prepare" stage of loading involves loading the target module,
verifying that the method described in 'entrypoint' exists, and determining which
files need to be processed.
"""
from pathlib import Path

from .structure import UserPluginSpec


def prepare(plug: UserPluginSpec, sandbox_base: Path):
    ...
