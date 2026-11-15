"""A kernel's Unix sockets go to $GRAFLANG_KERNEL_DIR, or a private temporary folder; never to the current folder."""
import os
import stat

import pytest

pytest.importorskip("jupyter_client")
pytestmark = pytest.mark.skipif(os.name != "posix", reason="Unix sockets are POSIX only")

from graphlang.grafr import kernel  # noqa: E402


def sockets(folder):
    return sorted(n for n in os.listdir(folder) if n.startswith("kernel-ipc"))


def test_sockets_go_to_the_chosen_folder(tmp_path, monkeypatch):
    start, chosen = tmp_path / "start", tmp_path / "kernels"
    start.mkdir()
    monkeypatch.chdir(start)
    monkeypatch.setenv("GRAFLANG_KERNEL_DIR", str(chosen))
    session = kernel.KernelSession()
    try:
        assert session.execute({"x": 2}, "y = x * 3", "y", 30) == 6
        assert sockets(chosen) and not sockets(start)
        assert stat.S_IMODE(os.stat(chosen).st_mode) == 0o700
    finally:
        session.close()


def test_default_is_a_private_temp_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GRAFLANG_KERNEL_DIR", raising=False)
    prefix = kernel.ipc_prefix()
    assert os.path.isabs(prefix) and not prefix.startswith(str(tmp_path))
    assert os.path.basename(os.path.dirname(prefix)).startswith("graflang-kernels-")
