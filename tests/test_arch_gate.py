from pathlib import Path

import yaml
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafu.arch2mmd import validate
from graphlang.grafu.arch_drift import drift
from graphlang.grafu.arch_gate import gate
from graphlang.grafu.mmd2arch import roundtrip_arch


def _repo(root: Path, name: str, deps=(), scripts=(), tests=True):
    (root / name).mkdir()
    body = f'[project]\nname = "{name}"\nversion = "0.1"\ndependencies = {list(deps)!r}\n'.replace("'", '"')
    if scripts:
        body += "[project.scripts]\n" + "".join(f'{s} = "x:main"\n' for s in scripts)
    (root / name / "pyproject.toml").write_text(body, encoding="utf-8")
    if tests:
        (root / name / "tests").mkdir()
        (root / name / "tests" / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")


def _arch(app_status="product", lib_status="product", lib_contract=None, app_contract=None):
    return {"arch": 1, "rules": {"edges_point_down": True}, "layers": [
        {"id": "apps", "rank": 2, "title": "Apps", "nodes": [{"id": "app", "name": "app", "cmd": ["app"], "pkg": "app", "repo": "app", "status": app_status,
                                                              "contract": app_contract or {"tests": ["tests"], "guarantees": ["it runs"]}}]},
        {"id": "libs", "rank": 1, "title": "Libs", "nodes": [{"id": "lib", "name": "lib", "pkg": "lib", "repo": "lib", "status": lib_status,
                                                              "contract": lib_contract or {"tests": ["tests"], "guarantees": ["it works"]}}]}],
        "edges": [{"from": "app", "to": "lib"}]}


def _both(tmp_path, **kw):
    _repo(tmp_path, "app", deps=["lib"], scripts=["app"])
    _repo(tmp_path, "lib")
    return {g.node: g for g in gate(_arch(**kw), tmp_path)}


def test_everything_earned_holds(tmp_path):
    g = _both(tmp_path)
    assert g["app"].earned == g["lib"].earned == "product" and g["app"].ok and g["lib"].ok


def test_product_needs_guarantees(tmp_path):
    g = _both(tmp_path, lib_contract={"tests": ["tests"]})
    assert g["lib"].earned == "validated" and not g["lib"].ok and "guarantees" in g["lib"].blockers[0]


def test_a_product_cannot_rest_on_a_lesser_dependency(tmp_path):
    g = _both(tmp_path, lib_status="validated", lib_contract={"tests": ["tests"]})
    assert g["lib"].ok and g["lib"].earned == "validated"       # claims only validated: fine
    assert not g["app"].ok and g["app"].earned == "validated" and "requires 'lib'" in g["app"].blockers[0]


def test_validated_needs_tests_that_exist(tmp_path):
    _repo(tmp_path, "app", deps=["lib"], scripts=["app"], tests=False)
    _repo(tmp_path, "lib")
    g = {x.node: x for x in gate(_arch(app_status="validated"), tmp_path)}
    assert not g["app"].ok and g["app"].earned == "prototype" and "no tests" in g["app"].blockers[0]


def test_a_missing_repo_earns_nothing(tmp_path):
    _repo(tmp_path, "lib")
    g = {x.node: x for x in gate(_arch(app_status="prototype"), tmp_path)}
    assert not g["app"].ok and g["app"].earned == "planned"


def test_drift_blocks_validated(tmp_path):
    _repo(tmp_path, "app", deps=[], scripts=["app"])             # the graph requires lib; the code does not
    _repo(tmp_path, "lib")
    g = {x.node: x for x in gate(_arch(app_status="validated"), tmp_path)}
    assert not g["app"].ok and "drift" in g["app"].blockers[0]


def test_unrated_nodes_are_not_gated(tmp_path):
    arch = _arch()
    del arch["layers"][1]["nodes"][0]["status"]
    _repo(tmp_path, "app", deps=["lib"], scripts=["app"])
    _repo(tmp_path, "lib")
    g = {x.node: x for x in gate(arch, tmp_path)}
    assert g["lib"].claimed is None and g["lib"].ok
    assert not g["app"].ok and "no status" in g["app"].blockers[0]       # a product cannot rest on an unrated component


def test_unknown_and_unlisted_commands_are_drift(tmp_path):
    _repo(tmp_path, "app", deps=["lib"], scripts=["app", "extra"])
    _repo(tmp_path, "lib")
    arch = _arch()
    arch["layers"][0]["nodes"][0]["cmd"] = ["app", "my-pip-name"]
    codes = sorted((f.code, f.is_error) for f in drift(arch, tmp_path))
    assert codes == [("unknown-command", True), ("unlisted-command", False)]


def test_contract_shape_is_validated_and_round_trips():
    arch = _arch()
    assert validate(arch)[0] == [] and roundtrip_arch(arch) == []
    arch["layers"][0]["nodes"][0]["contract"] = {"tests": "tests", "bogus": []}
    errors = validate(arch)[0]
    assert any("bogus" in e for e in errors) and any("list of strings" in e for e in errors)


def test_cli_exit_status(tmp_path):
    _repo(tmp_path, "app", deps=["lib"], scripts=["app"])
    _repo(tmp_path, "lib")
    f = tmp_path / "a.arch.yaml"
    f.write_text(yaml.safe_dump(_arch()), encoding="utf-8")
    r = CliRunner()
    assert r.invoke(main, ["util", "arch-gate", str(f), "--root", str(tmp_path)]).exit_code == 0
    f.write_text(yaml.safe_dump(_arch(lib_contract={"tests": ["tests"]})), encoding="utf-8")
    out = r.invoke(main, ["util", "arch-gate", str(f), "--root", str(tmp_path)])
    assert out.exit_code == 1 and "GATE FAILED" in out.output
