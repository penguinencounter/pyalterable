import contextlib
import logging
import os
import shutil
from collections import defaultdict
from glob import glob
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NoReturn, Optional

from rich.logging import RichHandler

from .configloader import load as load_config
from .runner import run_steps
from .resolves import compute as solve_compute
from ..contrib import list_builtins
from ..plugins.structure import UserPluginSpec, PluginSpec

logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s: %(message)s",
    handlers=[RichHandler(show_path=False)],
)
log = logging.getLogger("core")


def stop(reason: str) -> NoReturn:
    log.fatal(f"{reason}")
    exit(1)


def collect(targets: list[str]) -> list[str]:
    """
    Collection phase. Find source files and put their paths into a list.
    """
    paths = []
    for target in targets:
        globs = glob(target)
        for path in globs:
            paths.append(path)
    return paths


@contextlib.contextmanager
def prepare_env(sources: list[str]):
    """
    Copy files into a new, temporary directory.
    """
    with TemporaryDirectory() as tmpdir:
        log.debug(
            "Created temporary directory %s from %d sources", tmpdir, len(sources)
        )
        for source in sources:
            if os.path.isdir(source):
                name = os.path.basename(source)
                shutil.copytree(source, os.path.join(tmpdir, name))
            else:
                shutil.copy(source, tmpdir)
        yield tmpdir


def check_deps_simple(
    plugin_list: list[PluginSpec], requirements: dict[str, list[str]]
):
    available_names: set[str] = set()
    provides: dict[str, list[PluginSpec]] = defaultdict(list)
    for plugin in plugin_list:
        for provided in plugin.provides:
            provides[provided].append(plugin)
            available_names.add(provided)
    missing = set(requirements.keys()) - available_names
    if len(missing) > 0:
        names = []
        for name in missing:
            names.append(f"'{name}' (from {', '.join(requirements[name])})")
        stop(f"Plugin dependency error: unmet requirements: {', '.join(names)}")
    else:
        log.info(
            f"Plugin check first pass OK; {len(available_names)} slots provided, "
            f"{len(requirements)} slots requested."
        )
    return available_names, provides


def check_deps_complex(
    plugin_list: list[PluginSpec], providers: dict[str, list[PluginSpec]]
):
    def check(
        target: PluginSpec,
        current: Optional[PluginSpec] = None,
        visited: Optional[list[str]] = None,
    ):
        if visited is None:
            visited = list()
        if current is None:
            current = target
        if current.name in visited:
            log.warning(
                f"Plugins: while resolving '{current.name}' for '{target.name}': circular dependency "
                f"{' -> '.join(visited)} -> {current.name}"
            )
            return False, {}
        visited.append(current.name)

        for slot in current.use:
            valid_deps_from_here = set()
            for i, provider in enumerate(providers[slot]):
                if i > 0:
                    log.info(
                        f"attempt #{i + 1}: resolve '{slot}' dependency with '{provider.name}'"
                    )
                ok, extra = check(
                    target=target, current=provider, visited=visited.copy()
                )
                if ok:
                    valid_deps_from_here.add(provider.name)
                    break
            if len(valid_deps_from_here) == 0:
                log.warning(
                    f"Plugins: no plugin providing '{slot}' (used by {current.name}) "
                    f"can resolve when starting with {target.name}"
                )
                return False, (
                    f"\nall {len(providers[slot])} plugins providing '{slot}' "
                    f"can't be resolved when starting with {target.name}"
                )
        return True, None

    for plugin in plugin_list:
        check_ok, check_info = check(plugin)
        if not check_ok:
            stop(
                f"Plugin dependency error: cannot satisfy requirements for '{plugin.name}': {check_info}"
            )


def run_cli() -> int:
    conf_path = os.environ.get("ALTER_CONF", "alter.yaml")
    if not os.path.exists(conf_path):
        stop(
            f"No configuration file found at {conf_path}. "
            f"Set ALTER_CONF or create alter.toml in the working directory."
        )
    conf = load_config(conf_path).data

    # Collect
    collect_conf = conf.get("collect", {})
    if "rules" not in collect_conf:
        stop("No input rules specified (collect.rules does not exist)")
    rules = collect_conf["rules"]
    if not isinstance(rules, list):
        stop(f"Invalid type: collect.rules should be list, is actually {type(rules)}")
    if len(rules) == 0:
        stop("No input rules specified (collect.rules is empty)")
    sources = collect(rules)
    log.info("%d sources", len(sources))

    raw_plugins = conf.get("plugins", {})
    if not isinstance(raw_plugins, dict):
        stop(f"Invalid type: 'plugins' should be a dict")
    plugins: list[PluginSpec] = [
        UserPluginSpec.load(k, v) for k, v in raw_plugins.items()
    ] + list_builtins()

    # Collect a set of every slot needed at any point
    pre_conf = conf.get("preprocess", {})

    all_requirements: defaultdict[str, list[str]] = defaultdict(list)
    for plugin in plugins:
        for slot in plugin.use:
            all_requirements[slot].append(f"'{plugin.name}' plugin")
    if "use" in pre_conf:
        if not isinstance(pre_conf["use"], list):
            stop(
                f"Invalid type: preprocess.use should be list, is actually {type(pre_conf['use'])}"
            )
        for slot in pre_conf["use"]:
            all_requirements[slot].append("'preprocess' action")
    mapped_plugins = {p.name: p for p in plugins}
    available_slots, providers = check_deps_simple(plugins, all_requirements)
    # check_deps_complex(plugins, providers)
    log.info("%d plugins ready", len(raw_plugins))

    with prepare_env(sources) as presrc:
        tempdir = Path(presrc)
        # Pre-process
        if "use" not in pre_conf:
            log.info("no pre-processing specified, skipping")
        else:
            log.debug("Pre-processing in %s", presrc)
            pre_use = pre_conf["use"]
            if not isinstance(pre_use, list):
                stop(
                    f"Invalid type: preprocess.use should be list, is actually {type(pre_use)}"
                )
            solve_ok, steps = solve_compute(
                mapped_plugins, providers, "preprocess", pre_use
            )
            if not solve_ok:
                stop("Preprocessing failed.")
            try:
                run_steps(tempdir, steps, mapped_plugins)
            except Exception as e:
                log.critical(
                    f"Preprocessing [bold red]failed[/] because of [red][bold]{type(e).__name__}[/]: "
                    f"[italic]{e}[/][/]",
                    extra={"markup": True},
                )
                exit(1)
    return 0


if __name__ == "__main__":
    exit(run_cli())
