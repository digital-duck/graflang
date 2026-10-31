#!/usr/bin/env python3
"""`graf`: the one command line for GraphLang (run, validate, info, expand, compile, vis)."""
import copy

import click

from .grafc.cli import cmd_compile
from .grafr.cli import cmd_expand, cmd_info, cmd_run, cmd_validate
from .grafv.cli import cmd_vis


@click.group(help="GraphLang: graph-first agentic workflows. Run, validate, compile and draw a *.graph.yaml.",
             epilog="Base package: zinet  https://www.piwheels.org/project/zinet/",
             context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


for _cmd in (cmd_run, cmd_validate, cmd_info, cmd_compile, cmd_vis, cmd_expand):
    main.add_command(_cmd)

_viz = copy.copy(cmd_vis)                       # `graf viz` is `graf vis` under the spelling people type; the vis summary names it
_viz.hidden = True
main.add_command(_viz, "viz")
_ui = copy.copy(cmd_vis)                        # and `graf ui`, the name of the editor mode
_ui.hidden = True
main.add_command(_ui, "ui")


if __name__ == "__main__":
    main()
