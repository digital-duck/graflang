"""Port a lifted recipe (cookbook_solvers/NAME or cookbook_pocketflow/NAME) to the layered form (cookbook_solvers_v2/NAME, cookbook_pocketflow_v2/NAME).

    python scripts/port_recipe.py solvers NAME [NAME ...]       the two-arm shape below, grouped automatically
    python scripts/port_recipe.py pocketflow NAME --list        the steps, named, to choose groups from
    python scripts/port_recipe.py pocketflow NAME part=step,step part2=step,step ...     explicit groups (graf group, in this order)

The lifted solver recipes share one shape: some setup steps, a gate on the solver switch, the solver arm, a second gate, the LLM-only arm, the exit.
This script copies the recipe, compacts it, names every step after the tool or prompt it runs (tool_3 -> validate_schema), groups the setup
into `prepare`, the first arm into `solver_arm` and the second into `llm_only` (graf group), writes the parts as steps and prettifies every
file. A recipe that does not have that shape (not exactly two gates) is reported and left alone. Needs the `graf` command on the PATH.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {"solvers": (ROOT / "cookbook_solvers", ROOT / "cookbook_solvers_v2"), "pocketflow": (ROOT / "cookbook_pocketflow", ROOT / "cookbook_pocketflow_v2")}
SRC = DST = None
SKIP = shutil.ignore_patterns("output", ".graf", "__pycache__", "prettify_recipes.sh")
yaml = YAML()
yaml.width = 10 ** 9           # never wrap a long quoted string: a wrapped one can lose its line ends
yaml.preserve_quotes = True


def graf(*args):
    r = subprocess.run(["graf", *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"graf {' '.join(map(str, args))}: {(r.stdout + r.stderr).strip()[-400:]}")
    return r.stdout


def kind(step):
    return "evaluate" if "evaluate" in step else "generate" if "generate" in step else "assert" if "assert" in step else "output" if "output" in step else step.get("node", "?")


def rename_refs(value, mapping):
    """Replace step names in a reference: a string 'tool_3' or 'tool_3.port', or a list of them."""
    if isinstance(value, str):
        head, dot, rest = value.partition(".")
        return mapping.get(head, head) + dot + rest
    if isinstance(value, list):
        return [rename_refs(v, mapping) for v in value]
    return value


def new_names(steps):
    names, used = {}, set()

    def unique(base):
        base = re.sub(r"\W+", "_", base).strip("_") or "step"
        n, i = base, 2
        while n in used:
            n, i = f"{base}_{i}", i + 1
        used.add(n)
        return n
    for name, step in steps:
        k = kind(step)
        if k == "output":
            names[name] = name
        elif step.get("fork") is not None:
            names[name] = unique("fork")
        elif step.get("join") is not None:
            names[name] = unique("join")
        elif step.get("node") == "CONTEXT":
            names[name] = unique("set_" + str(step.get("out") or step.get("target_key") or name))
        elif k == "evaluate":
            expr = str(step["evaluate"])
            names[name] = unique("solver_on" if "'true'" in expr else "solver_off" if "'false'" in expr else "gate")
        elif k == "generate":
            names[name] = unique(str(step.get("function", name)).replace("_prompt", "").lstrip("_"))
        elif k == "assert":
            names[name] = None            # named below, after the steps it reads
        else:
            names[name] = unique(str(step.get("tool", name)).lstrip("_"))
    for name, step in steps:
        if names[name] is None:
            refs = [v for v in (step.get("in") or {}).values() if isinstance(v, str) and v in names and names[v]]
            names[name] = unique("assert_" + (names[refs[-1]] if refs else name))
    return names


def _as_text(data):
    import io
    buf = io.StringIO()
    yaml.dump(data, buf)
    return buf.getvalue()


def rename_all(data, names):
    """Apply `names` (old step id -> new) to the steps and to the long-form nodes and edges a recipe keeps beside them."""
    for item in data["steps"]:
        (old, step), = item.items()
        for key in ("in", "output", "fork", "join"):
            if key in step:
                v = step[key]
                if isinstance(v, dict):
                    for k2 in list(v):
                        v[k2] = rename_refs(v[k2], names)
                else:
                    step[key] = rename_refs(v, names)
        if "on" in step:
            step["on"] = rename_refs(step["on"], names)
    data["steps"] = [{names.get(list(i)[0], list(i)[0]): list(i.values())[0]} for i in data["steps"]]
    for node in data.get("nodes", []) or []:
        node["id"] = names.get(node["id"], node["id"])
    for edge in data.get("edges", []) or []:
        for end in ("source", "target"):
            edge[end] = rename_refs(edge[end], names)


def prepare(name, src, dst):
    """Copy the recipe, compact it and name its steps; returns (graph path, the data, the step names in order)."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=SKIP)
    graphs = sorted(dst.glob("*.graph.yaml"))
    if len(graphs) != 1:
        raise RuntimeError(f"{len(graphs)} graphs: not handled")
    path = graphs[0]
    graf("compact", path, "-o", path)
    data = yaml.load(path.read_text())
    steps = [(list(s)[0], list(s.values())[0]) for s in data["steps"]]
    names = new_names(steps)
    rename_all(data, names)
    with path.open("w") as f:
        yaml.dump(data, f)
    return path, data, steps, names


def port(family, name, groups=None):
    src_root, dst_root = FAMILIES[family]
    src, dst = src_root / name, dst_root / name
    path, data, steps, names = prepare(name, src, dst)
    order = [names[n] for n, _ in steps]
    if groups is None:                                           # the two-arm solver shape
        gates = [n for n, s in steps if kind(s) == "evaluate"]
        if len(gates) != 2:
            raise RuntimeError(f"{len(gates)} gates: not the two-arm shape")
        g1, g2 = names[gates[0]], names[gates[1]]
        i1, i2, ix = order.index(g1), order.index(g2), order.index("wf_exit")
        groups = [("prepare", order[:i1]), ("solver_arm", order[i1 + 1:i2]), ("llm_only", order[i2 + 1:ix])]
    for part, nodes in groups:
        if len(nodes) >= 1 and (len(nodes) >= 2 or part):
            graf("group", path, "--nodes", ",".join(nodes), "--name", part)
    for f in [path, *dst.glob("*/*.graph.yaml")]:
        if f != path:
            graf("compact", f, "-o", f)
        graf("prettier", f, "-o", f)
    graf("validate", path)
    original = (src / "readme.md").read_text() if (src / "readme.md").exists() else f"# {name}\n"
    original = original.replace(f"{src_root.name}/{name}", f"{dst_root.name}/{name}")
    parts = [p.name for p in sorted(dst.iterdir()) if p.is_dir() and (p / f"{p.name}.graph.yaml").exists()]
    head = (f"> **Layered port** of `{src_root.name}/{name}`: the same tools, prompts and gates, grouped into composites "
            f"({', '.join(f'`{p}/`' for p in parts)}), each step named after the tool or prompt it runs. "
            f"Checked against the original by `tests/test_{dst_root.name}.py`. Open it with `graf vis {dst_root.name}/{name}/{path.name} --depth 0`.\n\n")
    first, _, rest = original.partition("\n")
    (dst / "readme.md").write_text(first + "\n\n" + head + rest.lstrip("\n"))
    return parts


def listing(family, name):
    src_root, dst_root = FAMILIES[family]
    scratch = ROOT / "tmp" / "port_list" / name
    path, data, steps, names = prepare(name, src_root / name, scratch)
    for old, step in steps:
        extra = {k: step[k] for k in ("in", "on", "evaluate", "fork", "join", "loop") if k in step}
        print(f"{names[old]:28} {kind(step):9} {str(extra)[:150]}")
    for n in data.get("nodes", []) or []:
        print(f"  [long form] {n['id']:22} {n['type']}")
    shutil.rmtree(scratch.parent, ignore_errors=True)


if __name__ == "__main__":
    family, *rest = sys.argv[1:]
    DST = FAMILIES[family][1]
    DST.mkdir(exist_ok=True)
    if "--list" in rest:
        listing(family, rest[0])
        sys.exit()
    explicit = [a for a in rest if "=" in a]
    for n in [a for a in rest if "=" not in a]:
        groups = [(a.split("=", 1)[0], a.split("=", 1)[1].split(",")) for a in explicit] or None
        try:
            print(f"{n}: ported ({', '.join(port(family, n, groups))})")
        except Exception as e:            # report, go on with the next
            print(f"{n}: SKIPPED: {e}")
            shutil.rmtree(DST / n, ignore_errors=True)
