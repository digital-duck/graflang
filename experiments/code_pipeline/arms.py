"""The four arms. Each takes the spec text and a model and returns an ArmResult with the code it produced.

single     one coder call, the same prompt as step 1 of the pipeline (the floor: no review, no gate)
spl        SPL.py's orchestrator `code_pipeline.spl`, run by `spl3 run`
graflang   `cookbook/code_pipeline/code_pipeline.graph.yaml`, run by `graf run`
langgraph  the same pipeline written as a Python LangGraph program (lg_pipeline.py)

All four use the same adapter (claude_cli through the same CLI) and the same model, check_closure is off (it does not touch the
code), and everything else is the cookbook's default (max_cycles 3). A run that produces no code is a failure for the oracle.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPL_DIR = Path("/home/papagame/projects/digital-duck/SPL.py/cookbook/050_code_pipeline")
GRAPH = ROOT / "cookbook" / "code_pipeline" / "code_pipeline.graph.yaml"
ADAPTER = "claude_cli"
TIMEOUT = 1800


@dataclass
class ArmResult:
    code: str = ""
    seconds: float = 0.0
    status: str = "ok"                 # ok | no_code | error:<what>
    pipeline_verdict: str = ""         # the pipeline's own LLM "test" verdict on its final code: PASSED / FAILED / ""
    cycles: int = 0
    extra: dict = field(default_factory=dict)


def _verdict(text: str) -> str:
    return "PASSED" if "[PASSED]" in text else "FAILED" if "[FAILED]" in text else ""


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def run_single(spec: str, model: str) -> ArmResult:
    from graphlang.grafr.adapters import make_llm
    from lg_pipeline import fill, load_prompts
    from spl3.executor import _builtin_clean_code
    start = time.time()
    llm = make_llm(ADAPTER, model)
    code = _builtin_clean_code(llm.generate(fill(load_prompts(), "coder", spec=spec, lang="python"), model=model))
    return ArmResult(code=code, seconds=time.time() - start, status="ok" if code else "no_code", cycles=1)


def run_langgraph(spec: str, model: str) -> ArmResult:
    from graphlang.grafr.adapters import make_llm
    from lg_pipeline import build
    from spl3.executor import _builtin_clean_code
    start = time.time()
    try:
        final = build(make_llm(ADAPTER, model), model, _builtin_clean_code).invoke(
            {"spec": spec, "lang": "python", "max_cycles": 3}, {"recursion_limit": 60})
    except Exception as e:
        return ArmResult(seconds=time.time() - start, status=f"error:{type(e).__name__}: {str(e)[:150]}")
    code = final.get("code", "")
    status = "ok" if code else ("no_code" if "[READY]" not in final.get("analysis", "") else "error:empty")
    return ArmResult(code=code, seconds=time.time() - start, status=status, cycles=final.get("cycle", 0),
                     pipeline_verdict=_verdict(final.get("verdict", "")), extra={"spec_gate": "[READY]" in final.get("analysis", "")})


def run_spl(spec: str, model: str, work: Path) -> ArmResult:
    logs = work / "spl_logs"
    shutil.rmtree(logs, ignore_errors=True)
    start = time.time()
    cmd = ["spl3", "run", str(SPL_DIR / "code_pipeline.spl"), "--adapter", ADAPTER, "--model", model, "--persistence", "none",
           "--no-log", "-p", f"spec={spec}", "-p", f"pipeline_model={model}", "-p", "check_closure=false", "-p", f"log_dir={logs}"]
    try:
        done = _run(cmd, SPL_DIR)
    except subprocess.TimeoutExpired:
        return ArmResult(seconds=time.time() - start, status="error:timeout")
    code = _read(logs / "target" / "python" / "code.py")
    status = "ok" if code else ("no_code" if done.returncode == 0 else f"error:exit {done.returncode}: {done.stderr.strip()[-150:]}")
    return ArmResult(code=code, seconds=time.time() - start, status=status,
                     pipeline_verdict=_verdict(_read(logs / "tests" / "python" / "result.md")))


def run_graflang(spec: str, model: str, work: Path) -> ArmResult:
    artifacts = GRAPH.parent / ".grafr" / "logs"
    for sub in ("spec", "target", "tests"):
        shutil.rmtree(artifacts / sub, ignore_errors=True)
    start = time.time()
    cmd = [sys.executable, "-m", "graphlang", "run", str(GRAPH), "--llm", f"{ADAPTER}:{model}", "--no-log",
           "--output-dir", str(work / "graf_out"), "--param", f"spec={spec}", "--param", "check_closure=false"]
    try:
        done = _run(cmd, ROOT)
    except subprocess.TimeoutExpired:
        return ArmResult(seconds=time.time() - start, status="error:timeout")
    code = _read(artifacts / "target" / "python" / "code.py")
    status = "ok" if code else ("no_code" if done.returncode == 0 else f"error:exit {done.returncode}: {done.stderr.strip()[-150:]}")
    return ArmResult(code=code, seconds=time.time() - start, status=status,
                     pipeline_verdict=_verdict(_read(artifacts / "tests" / "python" / "result.md")))


ARMS = {"single": run_single, "spl": run_spl, "graflang": run_graflang, "langgraph": run_langgraph}
NEEDS_WORK_DIR = {"spl", "graflang"}
