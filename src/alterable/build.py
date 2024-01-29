import contextlib
import importlib
import importlib.util
import logging
import os
import shutil
import sys
from collections import defaultdict
from glob import glob
from hashlib import sha256
from tempfile import TemporaryDirectory
from typing import NamedTuple, NoReturn

from rich.logging import RichHandler
from strictyaml import load as loadyaml

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


class PluginPipelineInfo(NamedTuple):
    target: str

    @classmethod
    def load(cls, template: dict):
        return cls("file")


class AboutPlugin(NamedTuple):
    name: str
    provides: set[str]
    use: list[str]
    path: str
    pipeline: PluginPipelineInfo

    @classmethod
    def load(cls, name: str, template: dict):
        log.debug("Constructing plugin data for %s", name)
        provides = template.get("provides", [])
        provide_lst: set[str] = set()
        if isinstance(provides, str):
            provide_lst.add(provides)
        elif isinstance(provides, list):
            provide_lst.update(provides)
        else:
            stop(
                f"While loading plugin {name} info: 'provides' is not list or string or nothing (actually {provides=})"
            )
        provide_lst.add(name)
        use = template.get("use", [])
        if not isinstance(use, list):
            stop(
                f"While loading plugin {name} info: 'use' is not list or nothing (actually {use=})"
            )
        path = template.get("path")
        if path is None:
            stop(f"While loading plugin {name} info: no source path")

        pipeline_data = template.get("pipeline")
        if pipeline_data is None:
            stop(f"While loading plugin {name} info: no pipeline info")
        elif not isinstance(pipeline_data, dict):
            stop(
                f"While loading plugin {name} info: 'pipeline' is not table (actually {pipeline_data=})"
            )
        return cls(
            name=name,
            provides=provide_lst,
            use=use,
            path=path,
            pipeline=PluginPipelineInfo.load(pipeline_data),
        )


def load_plugin(about_plugin: AboutPlugin):
    hashn = sha256(about_plugin.name.encode()).hexdigest()
    full_name = f"_alter_generated.plugins.{hashn}"
    importspec = importlib.util.spec_from_file_location(full_name, about_plugin.path)
    if importspec is None:
        log.error("Cannot load a plugin from %s", about_plugin.path)


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


def run_cli():
    conf_path = os.environ.get("ALTER_CONF", "alter.yaml")
    if not os.path.exists(conf_path):
        stop(
            f"No configuration file found at {conf_path}. "
            f"Set ALTER_CONF or create alter.toml in the working directory."
        )
    with open(conf_path) as f:
        raw_conf = f.read()
    conf = loadyaml(raw_conf).data
    if not isinstance(conf, dict):
        stop(f"Invalid type: configuration should be a dict, is actually {type(conf)}")

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


if __name__ == "__main__":
    run_cli()
