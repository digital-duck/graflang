from pathlib import Path

import yaml
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafu.arch2mmd import load, to_mermaid, validate

BASE = {
    "arch": 1,
    "styles": {"app": {"fill": "#fff"}, "lib": {"fill": "#eee"}},
    "rules": {"edges_point_down": True, "requires_acyclic": True},
    "layers": [
        {"id": "apps", "rank": 2, "title": "Apps", "nodes": [{"id": "a", "name": "a", "style": "app"}]},
        {"id": "libs", "rank": 1, "title": "Libs", "nodes": [{"id": "b", "name": "b", "style": "lib"}, {"id": "c", "name": "c", "style": "lib"}]},
    ],
    "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c", "kind": "optional", "label": "x"}],
}


def _arch(**over):
    d = yaml.safe_load(yaml.safe_dump(BASE))
    d.update(over)
    return d


def test_valid_graph_draws_layers_edges_and_styles():
    mmd = to_mermaid(_arch())
    assert "layout: elk" in mmd and "flowchart TB" in mmd
    assert 'subgraph apps["2&nbsp;·&nbsp;Apps"]' in mmd
    assert "a --> b" in mmd and 'b -.->|"x"| c' in mmd
    assert "classDef app" in mmd and "class a app" in mmd


def test_edge_pointing_up_is_an_error():
    errors, _ = validate(_arch(edges=[{"from": "b", "to": "a"}]))
    assert any("points up" in e for e in errors)


def test_requires_cycle_and_unknown_node_are_errors():
    errors, _ = validate(_arch(edges=[{"from": "b", "to": "c"}, {"from": "c", "to": "b"}]))
    assert any("cycle" in e for e in errors)
    errors, _ = validate(_arch(edges=[{"from": "a", "to": "zzz"}]))
    assert any("unknown node" in e for e in errors)


def test_isolated_node_is_only_a_warning():
    errors, warnings = validate(_arch(edges=[{"from": "a", "to": "b"}]))
    assert not errors and any("'c'" in w for w in warnings)


def test_group_rows_get_invisible_links():
    arch = _arch(layers=[{"id": "libs", "rank": 1, "title": "Libs", "groups": [
        {"id": "g1", "title": "G1", "row": 1, "nodes": [{"id": "a", "name": "a"}]},
        {"id": "g2", "title": "G2", "row": 2, "nodes": [{"id": "b", "name": "b"}]}]}], edges=[])
    assert "a ~~~ b" in to_mermaid(arch)


def test_cli_writes_mmd_and_check_fails_on_rule_break(tmp_path):
    good = tmp_path / "x.arch.yaml"
    good.write_text(yaml.safe_dump(BASE), encoding="utf-8")
    r = CliRunner().invoke(main, ["util", "arch2mmd", str(good)])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "x.mmd").read_text(encoding="utf-8").startswith("---")
    bad = tmp_path / "bad.arch.yaml"
    bad.write_text(yaml.safe_dump(_arch(edges=[{"from": "b", "to": "a"}])), encoding="utf-8")
    r = CliRunner().invoke(main, ["util", "arch2mmd", str(bad), "--check"])
    assert r.exit_code != 0 and "points up" in r.output


def test_the_digital_duck_architecture_is_valid():
    p = Path("/home/papagame/projects/digital-duck/grafwork/graph-vision/digital-duck.arch.yaml")
    if p.exists():
        errors, _ = validate(load(p))
        assert not errors
