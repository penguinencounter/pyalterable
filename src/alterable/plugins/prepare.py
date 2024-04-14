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

from .shared_context import ProjectContext
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
    def __call__(
        self,
        pipe_info: FilePluginPipelineInfo,
        sandbox_base: Path,
        binding: Callable[..., None],
        context: ProjectContext,
    ) -> list[Callable[[], None]]:
        ...


class PartialPluginCallback(Protocol):
    def __call__(self, ctx: Any):
        ...


def match_project(
    pipe_info: FilePluginPipelineInfo,
    sandbox_base: Path,
    binding: Callable[..., None],
    context: ProjectContext,
) -> list[Callable[[], None]]:
    assert pipe_info.target == "project"
    return [functools.partial(binding, sandbox_base, context)]


def match_files(
    pipe_info: FilePluginPipelineInfo,
    sandbox_base: Path,
    binding: Callable[..., None],
    context: ProjectContext,
) -> list[Callable[[], None]]:
    assert pipe_info.target == "file"
    matching = []
    patterns = [re.compile(pat) for pat in pipe_info.rules]
    for dir_path, _, filenames in os.walk(sandbox_base):
        for file in filenames:
            full_path = Path(dir_path) / file
            if any(map(lambda pattern: pattern.search(str(full_path)), patterns)):
                matching.append(full_path)
    return [
        functools.partial(binding, path, context.files[str(path)]) for path in matching
    ]


def prepare(
    plug: PluginSpec, sandbox_base: Path, context: ProjectContext
) -> list[Callable[[], Any]]:
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
    bindings = list_builder(pipeline, sandbox_base, entrypoint, context)  # type: ignore
    return bindings
