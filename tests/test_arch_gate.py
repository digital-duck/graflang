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


def test_a_guarantee_that_cites_a_missing_test_blocks_product(tmp_path):
    g = _both(tmp_path, lib_contract={"tests": ["tests"], "guarantees": ["it works (tests/test_x.py::test_x)"]})
    assert g["lib"].earned == "product"                                 # test_x exists
    g = _both(tmp_path / "other", lib_contract={"tests": ["tests"], "guarantees": ["it works (tests/test_x.py::test_gone)"]}) if (tmp_path / "other").mkdir() is None else None
    assert not g["lib"].ok and g["lib"].earned == "validated" and "test_gone" in g["lib"].blockers[0]


def test_an_outside_service_without_a_repo_does_not_hold_a_product_back(tmp_path):
    arch = _arch()
    arch["layers"].append({"id": "outside", "rank": 0, "title": "Outside", "nodes": [{"id": "svc", "name": "hosted service"}]})
    arch["edges"].append({"from": "lib", "to": "svc"})
    _repo(tmp_path, "app", deps=["lib"], scripts=["app"])
    _repo(tmp_path, "lib")
    g = {x.node: x for x in gate(arch, tmp_path)}
    assert g["lib"].earned == "product" and g["app"].earned == "product"


# ---- --run-cited: the cited tests are run, and what happens to each counts -----------------------------------------------------------------

def _repo_with_tests(root: Path, name: str, body: str, conftest: str = ""):
    (root / name / "tests").mkdir(parents=True)
    (root / name / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1"\n', encoding="utf-8")
    (root / name / "tests" / "test_x.py").write_text(body, encoding="utf-8")
    if conftest:
        (root / name / "tests" / "conftest.py").write_text(conftest, encoding="utf-8")


def _cited_arch(*cites):
    return {"arch": 1, "layers": [{"id": "libs", "rank": 1, "title": "Libs", "nodes": [{
        "id": "lib", "name": "lib", "pkg": "lib", "repo": "lib", "status": "product",
        "contract": {"tests": ["tests"], "guarantees": [f"it works ({', '.join('tests/' + c for c in cites)})"]}}]}], "edges": []}


BODY = '''import pytest

def test_good():
    assert True

def test_bad():
    assert False

@pytest.mark.skip(reason="needs a server")
def test_skipped():
    pass

@pytest.mark.parametrize("n", [1, 2])
def test_param(n):
    assert n

class TestGroup:
    def test_in_a_class(self):
        assert True
'''


def test_run_cited_reports_passed_failed_skipped_and_missing(tmp_path):
    from graphlang.grafu.arch_gate import run_cited
    _repo_with_tests(tmp_path, "lib", BODY)
    arch = _cited_arch("test_x.py::test_good", "test_x.py::test_bad", "test_x.py::test_skipped", "test_x.py::test_param", "test_x.py::test_in_a_class")
    got = {e.name: e for e in run_cited(arch, tmp_path)["lib"]}
    assert {k: v.outcome for k, v in got.items()} == {"test_good": "passed", "test_bad": "failed", "test_skipped": "skipped", "test_param": "passed", "test_in_a_class": "passed"}
    assert "needs a server" in got["test_skipped"].detail


def test_a_failed_or_skipped_cited_test_blocks_product_and_a_passing_one_does_not(tmp_path):
    from graphlang.grafu.arch_gate import run_cited
    _repo_with_tests(tmp_path, "lib", BODY)
    good = _cited_arch("test_x.py::test_good", "test_x.py::test_in_a_class")
    assert gate(good, tmp_path, run_cited(good, tmp_path))[0].earned == "product"
    for bad_name in ("test_bad", "test_skipped"):
        arch = _cited_arch("test_x.py::test_good", f"test_x.py::{bad_name}")
        g = gate(arch, tmp_path, run_cited(arch, tmp_path))[0]
        assert g.earned == "validated" and not g.ok and bad_name in g.blockers[0]
    assert gate(_cited_arch("test_x.py::test_bad"), tmp_path)[0].earned == "product"       # without --run-cited the gate only checks that the test exists


def test_a_contract_mixin_in_conftest_is_collected_through_its_test_files(tmp_path):
    from graphlang.grafu.arch_gate import run_cited
    conftest = "class Contract:\n    def test_contract_rule(self):\n        assert True\n"
    _repo_with_tests(tmp_path, "lib", "from conftest import Contract\n\nclass TestImpl(Contract):\n    pass\n", conftest)
    arch = _cited_arch("conftest.py::test_contract_rule")
    assert [e.outcome for e in run_cited(arch, tmp_path)["lib"]] == ["passed"]


def test_run_cited_only_limits_the_nodes_and_a_missing_repo_is_an_error(tmp_path):
    from graphlang.grafu.arch_gate import run_cited
    arch = _cited_arch("test_x.py::test_good")
    assert run_cited(arch, tmp_path, only=["other"]) == {}
    assert [e.outcome for e in run_cited(arch, tmp_path)["lib"]] == ["error"]


def test_cli_run_cited_exit_status(tmp_path):
    _repo_with_tests(tmp_path, "lib", BODY)
    f = tmp_path / "a.arch.yaml"
    f.write_text(yaml.safe_dump(_cited_arch("test_x.py::test_good")), encoding="utf-8")
    r = CliRunner()
    assert r.invoke(main, ["util", "arch-gate", str(f), "--root", str(tmp_path), "--run-cited"]).exit_code == 0
    f.write_text(yaml.safe_dump(_cited_arch("test_x.py::test_good", "test_x.py::test_skipped")), encoding="utf-8")
    out = r.invoke(main, ["util", "arch-gate", str(f), "--root", str(tmp_path), "--run-cited"])
    assert out.exit_code == 1 and "test_skipped skipped" in out.output and "GATE FAILED" in out.output
