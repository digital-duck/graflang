from pathlib import Path

import yaml
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafu.arch_drift import drift, read_dependencies
from graphlang.grafu.mmd2arch import roundtrip_arch

ARCH = {
    "arch": 1,
    "layers": [
        {"id": "apps", "rank": 2, "title": "Apps", "nodes": [{"id": "app", "name": "app", "pkg": "my_app", "repo": "app"}]},
        {"id": "libs", "rank": 1, "title": "Libs", "nodes": [{"id": "core", "name": "core", "pkg": "core-lib", "repo": "core"},
                                                              {"id": "extra", "name": "extra", "pkg": "extra", "repo": "extra"}]},
    ],
    "edges": [{"from": "app", "to": "core"}, {"from": "app", "to": "extra", "kind": "optional"}],
}


def _repo(root: Path, name: str, pkg: str, deps=(), extras=()):
    (root / name).mkdir()
    lines = [f'[project]\nname = "{pkg}"\nversion = "0.1"\ndependencies = {list(deps)!r}\n'.replace("'", '"')]
    if extras:
        lines.append(f'[project.optional-dependencies]\nx = {list(extras)!r}\n'.replace("'", '"'))
    (root / name / "pyproject.toml").write_text("\n".join(lines), encoding="utf-8")


def test_matching_code_has_no_drift(tmp_path):
    _repo(tmp_path, "app", "my-app", deps=["core_lib>=1", "networkx"], extras=["extra[all]"])
    _repo(tmp_path, "core", "core-lib")
    _repo(tmp_path, "extra", "extra")
    assert drift(ARCH, tmp_path) == []


def test_drift_is_reported_both_ways(tmp_path):
    _repo(tmp_path, "app", "my-app", deps=["core-lib", "extra"])          # `extra` is required in the code, optional in the graph
    _repo(tmp_path, "core", "core-lib", deps=["extra"])                    # the graph has no edge core -> extra
    _repo(tmp_path, "extra", "other-name")                                 # pkg in the graph differs
    codes = sorted((f.code, f.node) for f in drift(ARCH, tmp_path))
    assert codes == [("missing-in-graph", "core"), ("stronger-in-code", "app"), ("wrong-package", "extra")]


def test_graph_edge_the_code_lacks_is_an_error(tmp_path):
    _repo(tmp_path, "app", "my-app", deps=["core-lib"])                    # no `extra` anywhere
    _repo(tmp_path, "core", "core-lib")
    _repo(tmp_path, "extra", "extra")
    f = drift(ARCH, tmp_path)
    assert [(x.code, x.node) for x in f] == [("missing-in-code", "app")] and f[0].is_error


def test_missing_repo_and_non_python_repo(tmp_path):
    _repo(tmp_path, "app", "my-app", deps=["core-lib"], extras=["extra"])
    (tmp_path / "core").mkdir()                                            # a repo without pyproject (e.g. Go): skipped, no finding
    assert [(f.code, f.node) for f in drift(ARCH, tmp_path)] == [("missing-repo", "extra")]


def test_hidden_edge_stays_in_graph_but_round_trips():
    arch = yaml.safe_load(yaml.safe_dump(ARCH))
    arch["edges"].insert(1, {"from": "app", "to": "core", "kind": "optional", "label": "x", "draw": False})
    assert roundtrip_arch(arch) == []


def test_cli_exit_status(tmp_path):
    _repo(tmp_path, "app", "my-app", deps=["core-lib"], extras=["extra"])
    _repo(tmp_path, "core", "core-lib")
    _repo(tmp_path, "extra", "extra")
    a = tmp_path / "x.arch.yaml"
    a.write_text(yaml.safe_dump(ARCH), encoding="utf-8")
    assert CliRunner().invoke(main, ["util", "arch-drift", str(a), "--root", str(tmp_path)]).exit_code == 0
    (tmp_path / "app" / "pyproject.toml").write_text('[project]\nname = "my-app"\nversion = "0.1"\n', encoding="utf-8")
    assert CliRunner().invoke(main, ["util", "arch-drift", str(a), "--root", str(tmp_path)]).exit_code == 1


def test_read_dependencies_normalizes_names(tmp_path):
    _repo(tmp_path, "r", "My_Pkg", deps=["Zi_Net>=0.2", "graflang[kernel]>=0.3"])
    assert read_dependencies(tmp_path / "r" / "pyproject.toml") == ("my-pkg", {"zi-net", "graflang"}, set())
