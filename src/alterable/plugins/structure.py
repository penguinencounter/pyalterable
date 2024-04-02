from __future__ import annotations

import importlib.util as import_util
import sys
from hashlib import sha256
from types import ModuleType
from typing import NamedTuple
import logging

from strictyaml import Seq, Str, Validator

from alterable.util import mk_stop

log = logging.getLogger("core.plugin")
stop = mk_stop(log)


class PluginData(object):
    PIPELINE_TARGET = "target"
    PIPELINE_TARGET_VALID = ["file", "project"]
    RULES: dict[str, dict[str, Validator]] = {
        "file": {"match": Seq(Str())},
        "project": {},
    }


class PluginPipelineInfo(NamedTuple):
    target: str

    @classmethod
    def load(cls, template: dict):
        return cls("file")


class PluginSpec:
    def __init__(
        self,
        name: str,
        *,
        provides: set[str],
        use: list[str],
        pipeline: PluginPipelineInfo,
    ):
        self.use = use
        self.provides = provides
        self.name = name
        self.pipeline = pipeline

    def resolve(self) -> ModuleType:
        raise NotImplementedError("can't resolve() abstract PluginSpec")


class PreloadPluginSpec(PluginSpec):
    def __init__(
        self,
        name: str,
        *,
        provides: set[str],
        use: list[str],
        pipeline: PluginPipelineInfo,
        module: ModuleType,
    ):
        super().__init__(name=name, provides=provides, use=use, pipeline=pipeline)
        self.module = module

    def resolve(self) -> ModuleType:
        return self.module


class UserPluginSpec(PluginSpec):
    def __init__(
        self,
        name: str,
        *,
        provides: set[str],
        use: list[str],
        pipeline: PluginPipelineInfo,
        path: str,
    ):
        super().__init__(name, provides=provides, use=use, pipeline=pipeline)
        self.path = path

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


def load_user_plugin(about_plugin: UserPluginSpec) -> ModuleType | None:
    hash_name = sha256(about_plugin.name.encode()).hexdigest()
    full_name = f"_alter_generated.plugins.{hash_name}"
    import_spec = import_util.spec_from_file_location(full_name, about_plugin.path)
    if import_spec is None:
        log.error("Cannot load a plugin from %s", about_plugin.path)
        return None
    module = import_util.module_from_spec(import_spec)
    sys.modules[full_name] = module
    import_spec.loader.exec_module(module)
    return module


def run_plugin(plugin: ModuleType, about: UserPluginSpec):
    entrypoint = about
