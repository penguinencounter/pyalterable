import contextlib
import logging
import os
import shutil
import sys
from collections import defaultdict
from glob import glob
from tempfile import TemporaryDirectory
from typing import NoReturn

from rich.logging import RichHandler
from strictyaml import load as loadyaml

from alterable.build import configloader
from ..api.plugin import AboutPlugin

logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s", handlers=[RichHandler()])
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
        log.debug("Created temporary directory %s from %d sources", tmpdir, len(sources))
        for source in sources:
            if os.path.isdir(source):
                name = os.path.basename(source)
                shutil.copytree(source, os.path.join(tmpdir, name))
            else:
                shutil.copy(source, tmpdir)
        yield tmpdir


def check_consistency(plugin_list: list[AboutPlugin], requirements: dict[str, list[str]]):
    available_names: set[str] = set()
    for plugin in plugin_list:
        for provided in plugin.provides:
            if provided in available_names:
                log.warning(f"Plugin: '{provided}' from more than one source.")
            available_names.add(provided)
    missing = set(requirements.keys()) - available_names
    if len(missing) > 0:
        names = []
        for name in missing:
            names.append(f"'{name}' (from {', '.join(requirements[name])})")
        stop(f"Plugin consistency error: unmet requirements: {', '.join(names)}")
    else:
        log.info(
            f"Plugin consistency check passed. {len(available_names)} slots provided, "
            f"{len(requirements)} slots requested."
        )
    return available_names


def run_cli() -> int:
    conf_path = os.environ.get("ALTER_CONF", "alter.yaml")
    if not os.path.exists(conf_path):
        stop(
            f"No configuration file found at {conf_path}. "
            f"Set ALTER_CONF or create alter.toml in the working directory."
        )
    conf = configloader.load(conf_path).data

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

    engine = os.environ.get("PYTHON_EXE", sys.executable)
    if not engine or not os.path.exists(engine):
        stop(
            f"Cannot find Python interpreter. Guessed {engine if engine else '(failed to retrieve)'}. "
            f"Set PYTHON_EXE to the path of a Python interpreter."
        )

    raw_plugins = conf.get("plugins", {})
    if not isinstance(raw_plugins, dict):
        stop(f"Invalid type: 'plugins' should be a dict")
    plugins = [AboutPlugin.load(k, v) for k, v in raw_plugins.items()]

    # Collect a set of every slot needed at any point
    pre_conf = conf.get("preprocess", {})

    all_requirements: defaultdict[str, list[str]] = defaultdict(list)
    for plugin in plugins:
        for slot in plugin.use:
            all_requirements[slot].append(f"'{plugin.name}' plugin")
    if "use" in pre_conf:
        if not isinstance(pre_conf["use"], list):
            stop(f"Invalid type: preprocess.use should be list, is actually {type(pre_conf['use'])}")
        for slot in pre_conf["use"]:
            all_requirements[slot].append("'preprocess' action")
    available_slots = check_consistency(plugins, all_requirements)
    log.info("%d plugins ready", len(raw_plugins))

    with prepare_env(sources) as presrc:
        # Pre-process
        if "use" not in pre_conf:
            log.info("no pre-processing specified, skipping")
        else:
            log.debug("Pre-processing in %s", presrc)
            pre_use = pre_conf["use"]
            if not isinstance(pre_use, list):
                stop(f"Invalid type: preprocess.use should be list, is actually {type(pre_use)}")
    return 0


if __name__ == "__main__":
    exit(run_cli())
