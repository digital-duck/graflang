#!/usr/bin/env python3
"""`graf`: the one command line for GraphLang (run, validate, info, compile, check, vis)."""
import click

from .grafc.cli import cmd_check, cmd_compile
from .grafr.cli import cmd_info, cmd_run, cmd_validate
from .grafv.cli import cmd_vis


@click.group(help="GraphLang: graph-first agentic workflows. Run, validate, compile and draw a *.graph.yaml.",
             context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


for _cmd in (cmd_run, cmd_validate, cmd_info, cmd_compile, cmd_check, cmd_vis):
    main.add_command(_cmd)


if __name__ == "__main__":
    main()
