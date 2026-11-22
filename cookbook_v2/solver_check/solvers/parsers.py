"""Custom parser for the solver_check example: graflang calls total(stdout) and expects an integer (the node's out_type)."""
import re


def total(stdout: str) -> int:
    match = re.search(r"^total: (-?\d+)$", stdout, re.M)
    if match is None:
        raise ValueError("no 'total: N' line in the solver's output")
    return int(match.group(1))
