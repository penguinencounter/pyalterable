import logging
import re
import textwrap
from os import PathLike

import rich
from rich.markup import escape
from strictyaml import (
    YAML,
    Any,
    Bool,
    EmptyDict,
    EmptyList,
    Enum,
    Map,
    MapPattern,
    Optional,
    Seq,
    Str,
    UniqueSeq,
    YAMLError,
)
from strictyaml import load as load_yaml
from strictyaml.ruamel.error import MarkedYAMLError
from strictyaml.validators import MapValidator, Validator
from strictyaml.yamllocation import YAMLChunk

from alterable.plugins.structure import PluginData

from ..util import mk_stop

log = logging.getLogger("core.configloader")
stop = mk_stop(log)
err_ctx = []


def _slots():
    return EmptyList() | UniqueSeq(Str())


def _patterns(allow_empty=True):
    if allow_empty:
        return EmptyList() | Seq(Str())
    return Seq(Str())


class _PipelineValidator(MapValidator):
    BASE_VALIDATOR: dict[str, Validator] = {
        "target": Enum(PluginData.PIPELINE_TARGET_VALID),
        "entrypoint": Str(),
    }
    OPTIONALS: dict[str, Validator] = {Optional("match"): Any()}

    def __init__(self):
        pass

    @staticmethod
    def validate(chunk: YAMLChunk):
        global err_ctx
        context = []
        err_ctx.append(context)
        # this better not be stateful
        Map(_PipelineValidator.BASE_VALIDATOR | _PipelineValidator.OPTIONALS).validate(
            chunk
        )
        mode: str | None = None
        mapping = chunk.expect_mapping()
        stringify = Str()
        for k, v in mapping:
            yaml_key = stringify(k)
            if yaml_key == PluginData.PIPELINE_TARGET:
                mode = stringify(v).data
                if mode not in PluginData.PIPELINE_TARGET_VALID:  # sanity check
                    stop(f"Invalid pipeline target: {mode!r}")
        assert mode in PluginData.PIPELINE_TARGET_VALID, "Invalid pipeline target"
        rules = PluginData.RULES[mode]
        if len(rules) == 0:
            context.append(
                f"info: Pipeline target {mode!r} requires no additional properties"
            )
        else:
            props = ", ".join(map(lambda x: f"{x!r}", rules.keys()))
            context.append(
                f"info: Pipeline target {mode!r} requires {len(rules)} additional properties: {props}"
            )

        combined = _PipelineValidator.BASE_VALIDATOR.copy()
        combined.update(rules)
        # Actual, final version
        Map(combined).validate(chunk)
        err_ctx.pop()


schema = Map(
    {
        "collect": Map(
            {
                "rules": _patterns(False),
            }
        ),
        Optional("preprocess"): EmptyDict()
        | Map({Optional("use"): _slots(), Optional("ordered"): Bool}),
        Optional("buildsystem"): EmptyDict()
        | MapPattern(
            Str(),
            Map(
                {
                    Optional("use"): _slots(),
                    Optional("exclude"): _patterns(True),
                }
            ),
        ),
        Optional("plugins"): EmptyDict()
        | MapPattern(
            Str(),
            Map(
                {
                    Optional("provides"): _slots(),
                    Optional("use"): _slots(),
                    "path": Str(),
                    "pipeline": _PipelineValidator(),
                }
            ),
        ),
    }
)


def load(conf_path: PathLike) -> YAML:
    with open(conf_path) as f:
        data = f.read()
    try:
        package = load_yaml(data, schema)
    except MarkedYAMLError as detail_e:
        context = []
        if detail_e.problem == "found a blank string":
            err_ctx.append(
                [
                    "hint: if you meant an empty sequence or mapping,\n"
                    "add additional data to create a mapping or sequence, try deleting the key entirely"
                ]
            )
        elif "unexpected key not in schema" in detail_e.problem:
            keyname = re.search(
                r"unexpected key not in schema ['\"](.*)['\"]$", detail_e.problem
            )
            if keyname is not None:
                err_ctx.append(
                    [f"hint: try removing {keyname.group(1)!r} and its contents"]
                )
        if len(context) > 0:
            err_ctx.append(context)
        all_messages: list[str] = [
            f"[bold red]{detail_e.context}: {detail_e.problem}[/]",
            f"[red]{detail_e.context}:[/]",
            f"{escape(str(detail_e.context_mark))}",
            f"[red]{detail_e.problem}:[/]",
            f"{escape(str(detail_e.problem_mark))}",
        ]

        if len(err_ctx) > 0:
            all_messages.append("\n[bold green]Additional information:[/]")
        counter = 0
        for i, stack in enumerate(err_ctx):
            for line in stack:
                col = "bright_cyan" if counter % 2 == 0 else "bright_blue"
                all_messages.append(f"[{col}]" + textwrap.indent(line, "  ") + "[/]")
                counter += 1
        out = "\n".join(all_messages)
        rich.print(out)
        stop("Invalid configuration. See above for details.")
    except YAMLError as generic_e:
        stop(str(generic_e))

    # respect my damn NoReturn annotations
    # noinspection PyUnboundLocalVariable
    return package
