"""
The "prepare" stage of loading involves loading the target module,
verifying that the method described in 'entrypoint' exists, and determining which
files need to be processed.
"""
import functools
import inspect
from pathlib import Path
from types import MappingProxyType
from typing import Callable, TypeVar, ParamSpec, Any, Literal

from .structure import PluginSpec

Ret = TypeVar("Ret")


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


def prepare(plug: PluginSpec, sandbox_base: Path):
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
                f'Bad entrypoint signature: {str(inspect.signature(entrypoint))}. '
                f'Target "{pipeline.target}" provides {description}.'
            )
            raise TypeError(error_msg)
    except KeyError as e:
        raise KeyError(
            f"while validating method signature: unknown pipeline target {pipeline.target}"
        ) from e
