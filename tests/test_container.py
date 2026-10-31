"""Running a subprocess solver in a container (`container:` on a subprocess SOLVE / RUN).

No Docker daemon is needed here: a stub `docker` on PATH checks what graflang asks for and runs the program locally. One test
uses a real daemon and is skipped without one (or without the python:3.12-slim image already pulled)."""
import json
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from graphlang.grafr.solve_backend import CODE_KEYS, check_solve
from graphlang.grafr.solver import SolverError, _docker_desktop, container_command, run_solver

STUB = '''#!{python}
import json, os, subprocess, sys
args = sys.argv[1:]
log = {log!r}
if args[0] == "info":
    import pathlib
    print(pathlib.Path(__file__).with_name("os_name").read_text())
    sys.exit(0)
if args[:2] == ["rm", "-f"]:
    open(log, "a").write(json.dumps({{"remove": args[2]}}) + "\\n")
    sys.exit(0)
i = args.index("img:1")
open(log, "a").write(json.dumps({{"flags": args[:i], "command": args[i + 1:], "env_has_secret": "SECRET" in os.environ,
                                 "env_has_home": "HOME" in os.environ}}) + "\\n")
sys.exit(subprocess.run(args[i + 1:], stdin=sys.stdin).returncode)
'''


@pytest.fixture
def docker(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "docker"
    log = tmp_path / "docker.log"
    stub.write_text(STUB.format(python=sys.executable, log=str(log)))
    (bin_dir / "os_name").write_text("Ubuntu 22.04")
    _docker_desktop.cache_clear()
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("SECRET", "hunter2")
    return lambda: [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_the_docker_command_is_locked_down_by_default(tmp_path):
    argv = container_command(["python", "check.py"], {"image": "img:1"}, base_dir=tmp_path, memory_mb=512, env_names=["TOKEN"], name="n")
    flags = " ".join(argv)
    assert argv[:3] == ["docker", "run", "--rm"] and argv[-3:] == ["img:1", "python", "check.py"]
    for part in ("--network none", "--read-only", "--cap-drop ALL", "no-new-privileges", "--memory 512m", "--pids-limit 128", f"{tmp_path.resolve()}:/work:ro", "-e TOKEN"):
        assert part in flags
    assert "hunter2" not in flags


def test_options_widen_only_what_they_name(tmp_path):
    argv = container_command(["x"], {"image": "i", "network": "bridge", "mount": "none", "cpus": 2, "memory_mb": 64}, base_dir=tmp_path, memory_mb=512, env_names=[], name="n")
    flags = " ".join(argv)
    assert "--network bridge" in flags and "-v" not in argv and "--cpus 2" in flags and "--memory 64m" in flags


def test_run_solver_goes_through_docker_and_gives_it_only_what_is_declared(docker, tmp_path):
    res = run_solver([sys.executable, "-c", "import json,sys; print(json.dumps({'n': json.load(sys.stdin)['a'] + 1}))"], {"a": 1},
                     parse="last_json", out_type="JSON", base_dir=tmp_path, container={"image": "img:1"})
    assert res.value == {"n": 2}
    (call,) = docker()
    assert "--network" in call["flags"] and call["flags"][call["flags"].index("--network") + 1] == "none"
    assert not call["env_has_secret"]                                                  # the caller's environment stays out
    assert "-e" not in call["flags"]


def test_a_declared_variable_reaches_the_container_by_name(docker, tmp_path):
    run_solver([sys.executable, "-c", "print('{}')"], {}, parse="last_json", out_type="JSON", base_dir=tmp_path,
               env={"TOKEN": "t"}, container={"image": "img:1"})
    (call,) = docker()
    assert call["flags"][call["flags"].index("-e") + 1] == "TOKEN" and "t" not in call["flags"]


def test_a_timeout_removes_the_container_not_just_the_client(docker, tmp_path):
    with pytest.raises(SolverError, match="timed out"):
        run_solver([sys.executable, "-c", "import time; time.sleep(30)"], {}, parse="last_json", out_type="JSON", base_dir=tmp_path,
                   timeout=1, container={"image": "img:1"})
    removed = [c for c in docker() if "remove" in c]
    assert len(removed) == 1 and removed[0]["remove"].startswith("graf-")


def test_a_missing_docker_is_an_error_about_docker(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(SolverError, match="docker command was not found"):
        run_solver(["x"], {}, parse="last_json", out_type="JSON", base_dir=tmp_path, container={"image": "img:1"})


def as_desktop(tmp_path):
    (tmp_path / "bin" / "os_name").write_text("Docker Desktop")
    _docker_desktop.cache_clear()


def run_in(base_dir, **container):
    return run_solver([sys.executable, "-c", "print('{}')"], {}, parse="last_json", out_type="JSON", base_dir=base_dir, container={"image": "img:1", **container})


def test_docker_desktop_refuses_a_folder_it_does_not_share_instead_of_hanging(docker, tmp_path):
    as_desktop(tmp_path)                                                   # tmp_path is under /tmp, not the home directory
    with pytest.raises(SolverError, match="shares only your home directory.*File sharing"):
        run_in(tmp_path)
    assert docker() == []                                                  # docker run was never started


def test_docker_desktop_accepts_home_a_listed_folder_or_no_mount(docker, tmp_path, monkeypatch):
    as_desktop(tmp_path)
    home_dir = Path(tempfile.mkdtemp(dir=Path.home()))
    try:
        assert run_in(home_dir).value == {}
    finally:
        shutil.rmtree(home_dir)
    run_in(tmp_path, mount="none")
    monkeypatch.setenv("GRAF_DOCKER_SHARED", f"/nonexistent:{tmp_path}")
    assert run_in(tmp_path).value == {}


def check(container):
    cfg = {"backend": "subprocess", "command": ["python", "x.py"], "container": container, "out_type": "JSON"}
    return check_solve({"id": "s", "type": "SOLVE", "ports": ["trigger", "complete", "out_r"], "config": cfg}, Path("."))


@pytest.mark.parametrize("container, message", [
    ("img", "mapping with an `image`"), ({}, "mapping with an `image`"), ({"image": "i", "net": 1}, "unknown key 'net'"),
    ({"image": "i", "network": "host"}, "'none' .* or 'bridge'"), ({"image": "i", "mount": "x"}, "container.mount"),
    ({"image": "i", "memory_mb": 0}, "container.memory_mb"),
])
def test_graf_validate_names_a_bad_container(container, message):
    errors, _ = check(container)
    assert any(__import__("re").search(message, e) for e in errors), errors


def test_a_good_container_is_accepted():
    assert check({"image": "python:3.12-slim"})[0] == []


def test_a_model_can_never_add_or_change_the_container():
    assert "container" in CODE_KEYS                                                    # removing it would remove the confinement


def _daemon_has_image():
    if shutil.which("docker") is None:
        return False
    try:
        done = subprocess.run(["docker", "image", "inspect", "python:3.12-slim"], capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        return False
    return done.returncode == 0


@pytest.mark.skipif(not _daemon_has_image(), reason="needs a running Docker daemon with python:3.12-slim pulled")
def test_real_docker_has_no_network_and_a_read_only_mount():
    _docker_desktop.cache_clear()
    folder = Path(tempfile.mkdtemp(dir=Path.home()))        # Docker Desktop shares the home directory, not /tmp
    try:
        (folder / "probe.py").write_text(
            "import json, socket, sys\n"
            "try:\n    socket.create_connection(('1.1.1.1', 53), timeout=2); net = True\nexcept OSError:\n    net = False\n"
            "try:\n    open('/work/new.txt', 'w'); wrote = True\nexcept OSError:\n    wrote = False\n"
            "try:\n    open('/etc/new.txt', 'w'); wrote_root = True\nexcept OSError:\n    wrote_root = False\n"
            "print(json.dumps({'net': net, 'wrote': wrote, 'wrote_root': wrote_root}))\n")
        res = run_solver(["python", "probe.py"], {}, parse="last_json", out_type="JSON", base_dir=folder, timeout=60, container={"image": "python:3.12-slim"})
        assert res.value == {"net": False, "wrote": False, "wrote_root": False} and not (folder / "new.txt").exists()
    finally:
        shutil.rmtree(folder)


@pytest.mark.skipif(not _daemon_has_image(), reason="needs a running Docker daemon with python:3.12-slim pulled")
def test_real_docker_runs_the_cookbook_graph_through_the_runtime():
    from graphlang.grafr.runtime import GraphLangRuntime, load_graph
    _docker_desktop.cache_clear()
    graph = load_graph(Path(__file__).parent.parent / "cookbook" / "container_demo" / "container_demo.graph.yaml")
    report = GraphLangRuntime(graph, verbose=False).execute({"numbers": "4,5,6"})["report"]
    assert report["sum"] == 15 and report["network"] is False and report["write_graph_folder"] is False and report["write_root"] is False
    assert report["hostname"] != __import__("socket").gethostname()                   # it really ran in another container


@pytest.mark.skipif(not _daemon_has_image(), reason="needs a running Docker daemon with python:3.12-slim pulled")
def test_real_docker_timeout_leaves_no_container_behind():
    _docker_desktop.cache_clear()
    with pytest.raises(SolverError, match="timed out"):
        run_solver(["python", "-c", "import time; time.sleep(60)"], {}, parse="last_json", out_type="JSON", base_dir=Path.home(), timeout=3,
                   container={"image": "python:3.12-slim", "mount": "none"})
    left = subprocess.run(["docker", "ps", "-a", "--filter", "name=graf-", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    assert left == []
