"""
The "prepare" stage of loading involves loading the target module,
verifying that the method described in 'entrypoint' exists, and determining which
files need to be processed.
"""
import functools
import inspect
import logging
import os
import re
from pathlib import Path
from typing import Callable, TypeVar, Protocol, Any

from .structure import (
    PluginSpec,
    PluginPipelineInfo,
    FilePluginPipelineInfo,
    ProjectPluginPipelineInfo,
)

Ret = TypeVar("Ret")
log = logging.getLogger("plugins.prepare")


def try_bind(target: Callable[..., Ret], args: int, kwargs: list[str] = None) -> bool:
    kwargs = kwargs or []
    signature = inspect.signature(target)
    try:
        test_args = [None] * args
        test_kwargs = {k: None for k in kwargs}
        signature.bind(*test_args, **test_kwargs)
        return True
    except TypeError:
        return False


PipelineT = TypeVar("PipelineT", bound=PluginPipelineInfo)


class _PathInstanceProvider(Protocol):
    def __call__(self, pipeline: PipelineT, sandbox_base: Path) -> list[Path]:
        ...


class PartialPluginCallback(Protocol):
    def __call__(self, ctx: Any):
        ...


def match_project(
    pipe_info: ProjectPluginPipelineInfo, sandbox_base: Path
) -> list[Path]:
    assert pipe_info.target == "project"
    return [sandbox_base]


def match_files(pipe_info: FilePluginPipelineInfo, sandbox_base: Path) -> list[Path]:
    assert pipe_info.target == "file"
    matching = []
    patterns = [re.compile(pat) for pat in pipe_info.rules]
    for dir_path, _, filenames in os.walk(sandbox_base):
        for file in filenames:
            full_path = Path(dir_path) / file
            if any(map(lambda pattern: pattern.search(str(full_path)), patterns)):
                matching.append(full_path)
    return matching


def prepare(plug: PluginSpec, sandbox_base: Path) -> list[PartialPluginCallback]:
    try:
        module = plug.resolve()
    except FileNotFoundError as e:
        raise ImportError(f"Cannot run plugin {plug}: {e}") from e
    except ImportError as e:
        raise ImportError(f"Cannot run plugin {plug}: {e}") from e

    pipeline = plug.pipeline
    entrypoint = getattr(module, pipeline.entrypoint, None)
    if entrypoint is None:
        raise ImportError(
            f"Cannot run plugin {plug}: described entrypoint {pipeline.entrypoint} doesn't exist"
        )

    # Check that the function signature makes sense in order to provide nice error messages
    arg_specs = {
        "project": (lambda func: try_bind(func, 2), "(project_path, build_context)"),
        "file": (lambda func: try_bind(func, 2), "(file_path, build_context)"),
    }
    try:
        arg_spec, description = arg_specs[pipeline.target]
        if not arg_spec(entrypoint):
            error_msg = (
                f"Bad entrypoint signature: {str(inspect.signature(entrypoint))}. "
                f'Target "{pipeline.target}" provides {description}.'
            )
            raise TypeError(error_msg)
    except KeyError as e:
        raise KeyError(
            f"while validating method signature: unknown pipeline target {pipeline.target}"
        ) from e

    sandbox_base = sandbox_base.absolute()
    list_builder: _PathInstanceProvider = {
        "project": match_project,
        "file": match_files,
    }[pipeline.target]
    targets = list_builder(pipeline, sandbox_base)

    bindings: list[PartialPluginCallback] = [
        functools.partial(entrypoint, target) for target in targets
    ]

    MAX_SHOW = 2
    more = ", ..." if len(targets) > MAX_SHOW else ""

    log.debug(
        f"bound [bright_blue]{plug.name}[/] to [bold green]{len(bindings)}[/] target(s): "
        f"{', '.join(map(str, targets[:MAX_SHOW]))}{more}",
        extra={"markup": True},
    )
    return bindings
