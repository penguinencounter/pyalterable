# it RESOLVES dependencies.
import logging
import time
from typing import TypeAlias, NamedTuple

from ..api.plugin import AboutPlugin, PluginPipelineInfo

log = logging.getLogger("resolver")

StacksType: TypeAlias = dict[str, tuple[str, "StacksType"]]

class DependencyResolutionError(RuntimeError):
    pass


def compute_plugin(target: AboutPlugin, providers: dict[str, list[AboutPlugin]]) -> tuple[bool, StacksType]:
    attempts = 0
    start = time.perf_counter()
    internal_log: list[str] = []

    def _log(msg: str):
        internal_log.append(msg)
        if len(internal_log) > 10:
            internal_log.pop(0)

    def _helper(at: AboutPlugin, visited: list[str]) -> tuple[bool, StacksType]:
        nonlocal attempts
        if at.name in visited:
            return False, {}
        visited.append(at.name)
        stacks: StacksType = {}

        for requirement in at.use:
            usable_dependencies: list[AboutPlugin] = []
            for provider in providers[requirement]:
                valid, stack_ = _helper(provider, visited.copy())
                attempts += 1
                if valid:
                    stacks[requirement] = (provider.name, stack_)
                    usable_dependencies.append(provider)
            if len(usable_dependencies) == 0:
                return False, {}

        return True, stacks.copy()

    result = _helper(target, [])
    end = time.perf_counter()
    if result[0]:
        log.info(f"plan created for {target.name}, {attempts} tries in {end-start:.4f}s")
    else:
        log.error(f"failed to make dependency plan for {target.name}, {attempts} tries in {end-start:.4f}s")
        return result
    return result


class DepLoadStruct(NamedTuple):
    name: str
    load_after: list[str] = []


# WIP TODO
def compute_load_order(plugins: dict[str, AboutPlugin], stacks: StacksType) -> list[str]:
    loaders: dict[str, DepLoadStruct] = {}
    def _traverse(substack: StacksType):
        for slot_name, solution in substack.items():
            if solution[0] not in loaders:
                loaders[solution[0]] = DepLoadStruct(solution[0], [])
            for k2, v2 in solution[1].items():
                if k2 not in loaders:
                    loaders[k2] = DepLoadStruct(k2, [slot_name])
                else:
                    loaders[k2].load_after.append(slot_name)
                _traverse(solution[1])
    return []


def compute(
    all_plugins: dict[str, AboutPlugin],
    providers: dict[str, list[AboutPlugin]],
    reason: str,
    requirements: list[str],
):
    anon = AboutPlugin(
        name=f"({reason} requirements: {', '.join(requirements)})",
        pipeline=PluginPipelineInfo("(anonymous)"),
        provides=set(),
        use=requirements,
        path="(anonymous)",
    )
    ok, result = compute_plugin(anon, providers)
    if not ok:
        return False, []
    log.info(result)
    load = compute_load_order(all_plugins, result)
