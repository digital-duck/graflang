#!/usr/bin/env python3
"""`graf`: the one command line for GraphLang (run, validate, info, compile, check, vis)."""
import copy

import click

from .grafc.cli import cmd_check, cmd_compile
from .grafe.cli import cmd_export_spl
from .grafr.cli import cmd_expand, cmd_info, cmd_run, cmd_validate
from .grafv.cli import cmd_vis


@click.group(help="GraphLang: graph-first agentic workflows. Run, validate, compile and draw a *.graph.yaml.",
             epilog="Base package: zinet  https://www.piwheels.org/project/zinet/",
             context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


for _cmd in (cmd_run, cmd_validate, cmd_info, cmd_compile, cmd_check, cmd_vis, cmd_expand, cmd_export_spl):
    main.add_command(_cmd)

_viz = copy.copy(cmd_vis)                       # `graf viz` is `graf vis` under the spelling people type; the vis summary names it
_viz.hidden = True
main.add_command(_viz, "viz")


if __name__ == "__main__":
    main()
