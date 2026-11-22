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
BY_IDS = False         # group members are the original (lifted) ids, whatever the steps are called now
MOVES = {}            # auto name -> the name chosen by hand (mv:old=new on the command line)
SKIP = shutil.ignore_patterns("output", ".graf", ".grafr", "logs-spl", "cookbook", "__pycache__", "prettify_recipes.sh")    # run results and logs are not part of a recipe
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
            solver = "solver" in expr
            names[name] = unique("solver_on" if solver and "'true'" in expr else "solver_off" if solver and "'false'" in expr else "gate")
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


def pseudo_step(node):
    """A long-form node as the compact form would spell it, for naming."""
    cfg = node.get("config") or {}
    t = node["type"]
    if t == "EVALUATE":
        return {"evaluate": str(cfg.get("condition") or cfg.get("expression") or "")}
    if t == "GENERATE":
        return {"generate": "", "function": cfg.get("function") or node["id"]}
    if t == "ASSERT":
        return {"assert": "", "in": {}}
    if t == "OUTPUT":
        return {"output": []}
    if t == "SOLVE":
        return {"node": "SOLVE", "tool": cfg.get("tool") or node["id"]}
    if t == "CONTEXT":
        return {"node": "CONTEXT", "out": cfg.get("target_key") or node["id"]}
    return {"node": t}


def prepare_graph(path):
    """Compact one graph file in place and name its steps; returns (the data, the steps, the new names)."""
    graf("compact", path, "-o", path)
    data = yaml.load(path.read_text())
    steps = [(list(s)[0], list(s.values())[0]) for s in data["steps"]]
    names = new_names(steps + [(n["id"], pseudo_step(n)) for n in data.get("nodes", []) or []])     # the long-form nodes are named the same way
    names = {old: MOVES.get(new, new) for old, new in names.items()}
    rename_all(data, names)
    with path.open("w") as f:
        yaml.dump(data, f)
    return data, steps, names


def copy_recipe(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=SKIP)
    graphs = sorted(dst.glob("*.graph.yaml"))
    if not graphs:
        raise RuntimeError("no graph")
    return graphs


def _on(step):
    on = step.get("on")
    return [on] if isinstance(on, str) else list(on or [])


def infer_groups(data):
    """Groups for the lifted solver shapes, from the renamed steps (and the long-form nodes beside them)."""
    steps = [(list(s)[0], list(s.values())[0]) for s in data["steps"]]
    order = [n for n, _ in steps]
    longform = [n["id"] for n in data.get("nodes", []) or [] if n["id"] != "wf_exit"]
    ix = order.index("wf_exit") if "wf_exit" in order else len(order)
    gates = [n for n, st in steps if kind(st) == "evaluate"]
    if any(n.startswith("set_use_solver") for n in order):        # the timed shape: normalise the switch, the direct arm, then the solver arm (a retry loop)
        mode_end = next(i for i, n in enumerate(order) if n.startswith("set_use_solver_2")) + 1
        mode_start = next(i for i, (n, st) in enumerate(steps) if "enable_solver" in str(st.get("in")) or "use_solver" in str(st.get("in")) and kind(st) != "evaluate")
        gate = next(n for n, st in steps[mode_end:] if kind(st) == "evaluate")
        gi = order.index(gate)
        solver_start = next((i for i, (n, st) in enumerate(steps) if f"{gate}.fail" in _on(st)), None)
        if solver_start is None:
            raise RuntimeError("timed shape without a solver arm")
        timing = [n for n in order[solver_start:ix] if n.startswith("time_")]
        arm_solver = [n for n in order[solver_start:ix] if n not in timing] + longform
        return [("mode", order[mode_start:mode_end]), ("llm_only", order[gi + 1:solver_start]), ("solver_arm", arm_solver)]
    if not gates:
        raise RuntimeError("no gate: not a solver shape")
    g = gates[0]
    gi = order.index(g)
    start2 = next((i for i, (n, st) in enumerate(steps) if f"{g}.fail" in _on(st)), None)
    if start2 is None:
        raise RuntimeError(f"nothing hangs on {g}.fail")
    if kind(steps[start2][1]) == "evaluate":                     # the switch is tested twice (on, then off): the second gate stays at the top
        arm1, arm2 = order[gi + 1:start2], order[start2 + 1:ix]
    else:
        arm1, arm2 = order[gi + 1:start2], order[start2:ix]
    if longform:                                                  # the solver arm is a retry loop, kept in long form; the timing steps stay at the top
        arm1 = [n for n in longform if not n.startswith("time_")]
        arm2 = [n for n in arm2 if not n.startswith("time_")]
    return [(part, nodes) for part, nodes in (("prepare", order[:gi]), ("solver_arm", arm1), ("llm_only", arm2)) if nodes]


def port(family, name, groups=None):
    """`groups`: a list of (part, [steps]) for a one-graph recipe, or {graph stem: that list} for several graphs; None infers the solver shape."""
    src_root, dst_root = FAMILIES[family]
    src, dst = src_root / name, dst_root / name
    graphs = copy_recipe(src, dst)
    many = len(graphs) > 1
    for path in graphs:
        stem = path.name.replace(".graph.yaml", "")
        data, steps, names = prepare_graph(path)
        chosen = groups.get(stem, []) if isinstance(groups, dict) else groups      # a graph left out of an explicit spec stays flat
        if chosen is None:
            try:
                chosen = infer_groups(data)
            except (RuntimeError, StopIteration) as e:
                if not many:
                    raise
                print(f"  {stem}: left flat ({e})")
                chosen = []
        if BY_IDS:                                                    # the groups name the original ids: the same spec serves graphs of one shape
            chosen = [(part, [names.get(n, n) for n in nodes]) for part, nodes in chosen]
        for part, nodes in chosen:
            if "/" in part:                                       # grouping inside a part: `rung/stage`
                inner, new = part.split("/", 1)
                inner = f"{stem}_{inner}" if many else inner
                graf("group", dst / inner / f"{inner}.graph.yaml", "--nodes", ",".join(nodes), "--name", new)
            else:
                graf("group", path, "--nodes", ",".join(nodes), "--name", f"{stem}_{part}" if many else part)
    for f in [*graphs, *sorted(dst.glob("*/*.graph.yaml")), *sorted(dst.glob("*/*/*.graph.yaml"))]:
        if f not in graphs:
            try:
                graf("compact", f, "-o", f)
            except RuntimeError:                 # a part with nothing to write as steps (a loop and its body) stays in long form
                pass
        graf("prettier", f, "-o", f)
    for path in graphs:
        graf("validate", path)
    original = (src / "readme.md").read_text() if (src / "readme.md").exists() else f"# {name}\n"
    original = original.replace(f"{src_root.name}/{name}", f"{dst_root.name}/{name}")
    parts = [p.name for p in sorted(dst.iterdir()) if p.is_dir() and list(p.glob("*.graph.yaml"))]
    head = (f"> **Layered port** of `{src_root.name}/{name}`: the same tools, prompts and gates, grouped into composites "
            f"({', '.join(f'`{p}/`' for p in parts)}), each step named after the tool or prompt it runs. "
            f"Checked against the original by `tests/test_{dst_root.name}.py`. Open it with `graf vis {dst_root.name}/{name}/{graphs[0].name} --depth 0`.\n\n")
    first, _, rest = original.partition("\n")
    (dst / "readme.md").write_text(first + "\n\n" + head + rest.lstrip("\n"))
    return parts


def listing(family, name):
    src_root, dst_root = FAMILIES[family]
    scratch = ROOT / "tmp" / "port_list" / name
    for path in copy_recipe(src_root / name, scratch):
        data, steps, names = prepare_graph(path)
        print(f"##### {path.name}")
        for old, step in steps:
            extra = {k: step[k] for k in ("in", "on", "evaluate", "fork", "join", "loop") if k in step}
            print(f"{names[old]:28} {kind(step):9} (was {old}) {str(extra)[:120]}")
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
    if "--ids" in rest:
        BY_IDS = True
        rest = [a for a in rest if a != "--ids"]
    for a in [a for a in rest if a.startswith("mv:")]:
        old, _, new = a[3:].partition("=")
        MOVES[old] = new
    rest = [a for a in rest if not a.startswith("mv:")]
    explicit = [a for a in rest if "=" in a]
    for n in [a for a in rest if "=" not in a]:
        groups = None
        if explicit:
            if any(":" in a.split("=", 1)[0] for a in explicit):          # stem:part=a,b  for a recipe with several graphs
                groups = {}
                for a in explicit:
                    key, nodes = a.split("=", 1)
                    stem, part = key.split(":", 1)
                    groups.setdefault(stem, []).append((part, nodes.split(",")))
            else:
                groups = [(a.split("=", 1)[0], a.split("=", 1)[1].split(",")) for a in explicit]
        try:
            print(f"{n}: ported ({', '.join(port(family, n, groups))})")
        except Exception as e:            # report, go on with the next
            print(f"{n}: SKIPPED: {e}")
            shutil.rmtree(DST / n, ignore_errors=True)
