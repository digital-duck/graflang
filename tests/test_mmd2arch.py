from pathlib import Path

import yaml
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafu.arch2mmd import load, to_mermaid
from graphlang.grafu.mmd2arch import roundtrip_arch, roundtrip_mmd, to_arch

ARCH = {
    "arch": 1, "name": "demo", "title": "Demo", "layout": "elk",
    "styles": {"app": {"fill": "#fff", "stroke": "#000"}, "lib": {"fill": "#eee"}},
    "group_styles": {"tint": {"fill": "#ddd", "stroke-width": "2px"}},
    "rules": {"edges_point_down": True, "requires_acyclic": True},
    "layers": [
        {"id": "apps", "rank": 2, "title": "Apps", "nodes": [
            {"id": "my-app", "name": "my-app", "cmd": ["myapp", "ma"], "summary": ["does `x`", "and y"], "pkg": "my-app", "style": "app"}]},
        {"id": "libs", "rank": 1, "title": "Libs", "groups": [
            {"id": "g1", "title": "Row one", "row": 1, "style": "tint", "nodes": [{"id": "lib-a", "name": "lib-a", "summary": ["A"], "style": "lib"}]},
            {"id": "g2", "title": "Row two", "row": 2, "style": "tint", "nodes": [{"id": "lib-b", "name": "lib-b", "note": "(Go)", "status": "prototype", "style": "lib"}]}]},
    ],
    "edges": [{"from": "my-app", "to": "lib-a", "label": "uses"}, {"from": "lib-a", "to": "lib-b", "kind": "network"}],
}


def test_arch_mmd_arch_is_lossless():
    assert roundtrip_arch(ARCH) == []


def test_reading_back_recovers_the_fields():
    arch = to_arch(to_mermaid(ARCH))
    app = arch["layers"][0]["nodes"][0]
    assert app["id"] == "my-app" and app["cmd"] == ["myapp", "ma"] and app["summary"] == ["does `x`", "and y"] and app["pkg"] == "my-app"
    g2 = arch["layers"][1]["groups"][1]
    assert g2["row"] == 2 and g2["style"] == "tint" and g2["nodes"][0]["status"] == "prototype" and g2["nodes"][0]["note"] == "(Go)"
    assert arch["edges"][1]["kind"] == "network" and arch["rules"]["requires_acyclic"] is True


def test_hand_written_mmd_round_trips_without_meta():
    mmd = '''flowchart TB
    subgraph TOP["2 · Top"]
        direction LR
        A["<b>A</b><br/>does a"]
    end
    subgraph LOW["1 · Low"]
        B["<b>B</b>"]
    end
    A -.->|"opt"| B
    classDef c fill:#fff
    class A,B c
'''
    assert roundtrip_mmd(mmd) == []
    arch = to_arch(mmd)
    assert [l["rank"] for l in arch["layers"]] == [2, 1] and arch["edges"][0]["kind"] == "optional"


def test_the_digital_duck_chart_round_trips():
    base = Path("/home/papagame/projects/digital-duck/grafwork/graph-vision")
    if (base / "digital-duck.arch.yaml").exists():
        assert roundtrip_arch(load(base / "digital-duck.arch.yaml")) == []
        assert roundtrip_mmd((base / "dd-techstack-chart.mmd").read_text(encoding="utf-8")) == []


def test_cli_verify_and_convert(tmp_path):
    a = tmp_path / "d.arch.yaml"
    a.write_text(yaml.safe_dump(ARCH), encoding="utf-8")
    r = CliRunner()
    assert r.invoke(main, ["util", "arch2mmd", str(a), "--verify"]).exit_code == 0
    assert r.invoke(main, ["util", "arch2mmd", str(a)]).exit_code == 0
    assert r.invoke(main, ["util", "mmd2arch", str(tmp_path / "d.mmd"), "--verify"]).exit_code == 0
    out = tmp_path / "back.arch.yaml"
    assert r.invoke(main, ["util", "mmd2arch", str(tmp_path / "d.mmd"), "-o", str(out)]).exit_code == 0
    assert yaml.safe_load(out.read_text(encoding="utf-8"))["layers"][0]["nodes"][0]["id"] == "my-app"
