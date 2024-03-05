# it RESOLVES dependencies.
import logging

from ..api.plugin import AboutPlugin, PluginPipelineInfo

log = logging.getLogger("resolver")


def compute_plugin(target: AboutPlugin, providers: dict[str, list[AboutPlugin]]):
    invalids = 0

    def _helper(at: AboutPlugin, visited: list[str], stack: list[str]) -> tuple[bool, list[str]]:
        nonlocal invalids
        if at.name in visited:
            return False, [at.name]
        visited.append(at.name)

        for requirement in at.use:
            usable_dependencies: list[AboutPlugin] = []
            for provider in providers[requirement]:
                valid, stack = _helper(provider, visited.copy(), [])
                if valid:
                    usable_dependencies.append(provider)
                else:
                    invalids += 1
            if len(usable_dependencies) == 0:
                return False, []

        return True, stack + [at.name]
    log.info(_helper(target, [], []))
    log.info(f"resolution complete, tried {invalids} invalid chains")


def compute(
    providers: dict[str, list[AboutPlugin]],
    reason: str,
    requirements: list[str],
):
    anon = AboutPlugin(
        name=f"(anonymous: {reason})",
        pipeline=PluginPipelineInfo("(anonymous)"),
        provides=set(),
        use=requirements,
        path="(anonymous)"
    )
    compute_plugin(anon, providers)
