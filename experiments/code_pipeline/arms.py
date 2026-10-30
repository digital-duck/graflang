"""The four arms. Each takes the spec text, a model and a run folder, and returns an ArmResult with the code it produced.

single     one coder call, the same prompt as step 1 of the pipeline (the floor: no review, no gate)
spl        SPL.py's orchestrator `code_pipeline.spl`, run by `spl3 run`
graflang   `cookbook/code_pipeline/code_pipeline.graph.yaml`, run by `graf run`
langgraph  the same pipeline written as a Python LangGraph program (lg_pipeline.py)

All four use the same adapter and model, check_closure is off (it does not touch the code), and everything else is the
cookbook's default (max_cycles 3). A run that produces no code is a failure for the oracle.

Each arm also reports, for every cycle it ran: the code the tester saw and the tester's verdict (`cycles_detail`), and the
LLM calls and tokens it used (`llm`). Tokens are the dd-llm estimate (characters / 4; the claude_cli adapter does not report
usage), the same convention for every arm, so they compare across arms but are not billing numbers.

Everything a run leaves behind goes into its run folder (`output/<adapter>/<model>/<task>/<arm>-rep<N>/`, git-ignored):
    single     code.py
    spl        code.py, spl/ (the trace log and the artifacts), prompts/ (every prompt sent, in order), stdout.txt
    graflang   code.py, logs/ (the graph and procedure logs as JSONL), graf_out/ (every node's output, one file per firing,
               numbered by step), prompts/<procedure>/ (every prompt sent, as spl), artifacts/, stdout.txt
    langgraph  code.py, state.json (the final state, including the per-cycle history)
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPL_PY = Path(os.environ.get("SPL_PY_PATH", ROOT.parent / "SPL.py"))   # SPL.py checkout
SPL_DIR = SPL_PY / "cookbook" / "050_code_pipeline"
GRAPH = ROOT / "cookbook" / "code_pipeline" / "code_pipeline.graph.yaml"
ADAPTER = os.environ.get("ADAPTER", "claude_cli")     # claude_cli (default), ollama, ... any dd-llm adapter; all four arms use it
TIMEOUT = 1800


@dataclass
class ArmResult:
    code: str = ""
    seconds: float = 0.0
    status: str = "ok"                 # ok | no_code | error:<what>
    pipeline_verdict: str = ""         # the pipeline's own LLM "test" verdict on its final code: PASSED / FAILED / ""
    cycles: int = 0                    # generate-review-improve-test cycles the pipeline used (1 for single)
    cycles_detail: list = field(default_factory=list)   # per cycle: {"cycle", "code", "verdict"} (verdict: PASSED/FAILED/"")
    llm: dict = field(default_factory=dict)              # {"calls", "prompt_tokens", "output_tokens"}
    extra: dict = field(default_factory=dict)


class CountingLLM:
    """Wraps the dd-llm object: counts calls and estimates tokens the same way dd-llm does (characters / 4)."""

    def __init__(self, inner):
        self.inner, self.calls, self.prompt_tokens, self.output_tokens = inner, 0, 0, 0

    def generate(self, prompt, model=None, **opts):
        text = self.inner.generate(prompt, model=model, **opts)
        self.calls += 1
        self.prompt_tokens += max(1, len(prompt) // 4)
        self.output_tokens += max(1, len(text or "") // 4)
        return text

    def totals(self) -> dict:
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens, "output_tokens": self.output_tokens}


def _verdict(text: str) -> str:
    return "PASSED" if "[PASSED]" in text else "FAILED" if "[FAILED]" in text else ""


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _save(run_dir: Path, code: str) -> None:
    (run_dir / "code.py").write_text(code, encoding="utf-8")


LIMIT_MARKERS = ("session limit", "usage limit", "rate limit", "limit reached", "quota")


def is_limit_error(text: str) -> bool:
    """True when a status or a log says the account hit a session, usage, rate or quota limit: the batch must stop."""
    lowered = (text or "").lower()
    return any(marker in lowered for marker in LIMIT_MARKERS)


def limit_in_folder(folder: Path) -> bool:
    """True when the run folder's saved stdout or error text reports a limit (some failures print it on stdout only)."""
    return any(is_limit_error((folder / name).read_text(encoding="utf-8", errors="replace"))
               for name in ("stdout.txt", "error.txt") if (folder / name).is_file())


def _finish(done: subprocess.CompletedProcess, code: str, start: float) -> tuple[str, float]:
    # the failure text is on stderr, or (for some adapters) only on stdout: keep the tail of whichever has it
    detail = done.stderr.strip() or done.stdout.strip()
    status = "ok" if code else ("no_code" if done.returncode == 0 else f"error:exit {done.returncode}: {detail[-150:]}")
    return status, time.time() - start


# The test step's prompt wraps the code between these two lines of the template (04_test_code.spl), so the code each cycle's
# tester saw can be read back from the prompt file. The text before and after the code is fixed by the template.
_TEST_CODE_START = "{lang} code to evaluate:\n"
_TEST_CODE_END = "\n\nEvaluate the code against the specification."


def _code_in_test_prompt(text: str, lang: str = "python") -> str:
    start = text.find(_TEST_CODE_START.format(lang=lang))
    end = text.find(_TEST_CODE_END, start)
    if start < 0 or end < 0:
        return ""
    return text[start + len(_TEST_CODE_START.format(lang=lang)):end]


_WORKFLOW_END = re.compile(r"workflow\.end workflow=(\S+) status=\S+ llm_calls=(\d+) input_tokens=(\d+) output_tokens=(\d+)")


def _spl_totals(lines, skip: str) -> dict:
    """Sum LLM calls and tokens over the sub-workflows' `workflow.end` records (the orchestrator's own record repeats
    the totals with zero tokens, so it is skipped)."""
    calls = ptok = otok = 0
    for line in lines:
        m = _WORKFLOW_END.search(line)
        if m and m.group(1) != skip:
            calls, ptok, otok = calls + int(m.group(2)), ptok + int(m.group(3)), otok + int(m.group(4))
    return {"calls": calls, "prompt_tokens": ptok, "output_tokens": otok}


def _spl_cycles(run_dir: Path, final_verdict: str, final_code: str) -> list[dict]:
    """One entry per cycle, from the test prompts in order. Every cycle but the last failed (the loop only repeats after
    a FAILED verdict), so their verdict is known; the last one is the pipeline's verdict on the final code."""
    tests = sorted((run_dir / "prompts").glob("run_tests_*.md"))
    out = []
    for i, path in enumerate(tests, start=1):
        last = i == len(tests)
        out.append({"cycle": i, "code": _code_in_test_prompt(path.read_text(encoding="utf-8")) if not last else final_code,
                    "verdict": (final_verdict if last else "FAILED")})
    return out


def run_single(spec: str, model: str, run_dir: Path) -> ArmResult:
    from graphlang.grafr.adapters import make_llm
    from lg_pipeline import fill, load_prompts
    from spl3.executor import _builtin_clean_code
    start = time.time()
    llm = CountingLLM(make_llm(ADAPTER, model))
    code = _builtin_clean_code(llm.generate(fill(load_prompts(), "coder", spec=spec, lang="python"), model=model))
    _save(run_dir, code)
    return ArmResult(code=code, seconds=time.time() - start, status="ok" if code else "no_code", cycles=1,
                     cycles_detail=[{"cycle": 1, "code": code, "verdict": ""}], llm=llm.totals())


def run_langgraph(spec: str, model: str, run_dir: Path) -> ArmResult:
    from graphlang.grafr.adapters import make_llm
    from lg_pipeline import build
    from spl3.executor import _builtin_clean_code
    start = time.time()
    llm = CountingLLM(make_llm(ADAPTER, model))
    try:
        final = build(llm, model, _builtin_clean_code).invoke(
            {"spec": spec, "lang": "python", "max_cycles": 3}, {"recursion_limit": 60})
    except Exception as e:
        return ArmResult(seconds=time.time() - start, status=f"error:{type(e).__name__}: {str(e)[:150]}", llm=llm.totals())
    code = final.get("code", "")
    _save(run_dir, code)
    (run_dir / "state.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    status = "ok" if code else ("no_code" if "[READY]" not in final.get("analysis", "") else "error:empty")
    return ArmResult(code=code, seconds=time.time() - start, status=status, cycles=final.get("cycle", 0),
                     pipeline_verdict=_verdict(final.get("verdict", "")), cycles_detail=list(final.get("history", [])),
                     llm=llm.totals(), extra={"spec_gate": "[READY]" in final.get("analysis", "")})


def run_spl(spec: str, model: str, run_dir: Path) -> ArmResult:
    logs = run_dir / "spl"
    start = time.time()
    # cwd is the run folder, so the `.spl/` working files spl3 creates land there and not in the SPL.py checkout
    cmd = [sys.executable, "-c", "from spl3.cli import main; main()", "run", str(SPL_DIR / "code_pipeline.spl"), "--adapter", ADAPTER, "--model", model, "--persistence", "none",
           "--log-prompts", str(run_dir / "prompts"), "-p", f"spec={spec}", "-p", f"pipeline_model={model}",
           "-p", "check_closure=false", "-p", f"log_dir={logs}"]
    try:
        done = _run(cmd, run_dir)
    except subprocess.TimeoutExpired:
        return ArmResult(seconds=time.time() - start, status="error:timeout")
    code = _read(logs / "target" / "python" / "code.py")
    _save(run_dir, code)
    status, seconds = _finish(done, code, start)
    (run_dir / "stdout.txt").write_text(done.stdout + "\n--- stderr ---\n" + done.stderr, encoding="utf-8")
    verdict = _verdict(_read(logs / "tests" / "python" / "result.md"))
    cycles = _spl_cycles(run_dir, verdict, code)
    trace = [p.read_text(encoding="utf-8", errors="replace").splitlines() for p in (run_dir / "spl").glob("code_pipeline-*.log")]
    return ArmResult(code=code, seconds=seconds, status=status, cycles=len(cycles), cycles_detail=cycles,
                     pipeline_verdict=verdict, llm=_spl_totals([line for lines in trace for line in lines], skip="code_pipeline"))


def _graf_cycles(run_dir: Path, final_verdict: str, final_code: str) -> list[dict]:
    """One entry per loop iteration. The verdicts come from the graph's `loop_eval` firings (pass or fail, in order); the
    code each cycle tested is the `loop_imp` output saved for that iteration (--save-nodes numbers files by step, so the
    iterations do not overwrite each other)."""
    verdicts, saved = [], []
    for line in (run_dir / "logs").glob("code_pipeline-*.jsonl"):
        for raw in line.read_text(encoding="utf-8", errors="replace").splitlines():
            rec = json.loads(raw)
            msg = rec.get("msg", "")
            if msg.startswith("node.done node=loop_eval") and "route=pass" in msg:
                verdicts.append("PASSED")
            elif msg.startswith("node.done node=loop_eval") and "route=fail" in msg:
                verdicts.append("FAILED")
            elif msg.startswith("node.saved") and "port=out_improved_code" in msg and rec.get("file"):
                saved.append(rec["file"])
    out = []
    for i, verdict in enumerate(verdicts, start=1):
        last = i == len(verdicts)
        code = final_code if last else (_read(Path(saved[i - 1])) if i - 1 < len(saved) else "")
        out.append({"cycle": i, "code": code, "verdict": verdict if not last or verdict else final_verdict})
    return out


GRAF_LOCK = ROOT / "experiments" / "code_pipeline" / "logs" / ".graflang.lock"


def run_graflang(spec: str, model: str, run_dir: Path) -> ArmResult:
    """The graph's procedures write their artifacts to one shared folder (graphlang's `.grafr/logs`), so only one graflang
    run may be in progress at a time, across processes: a second run would clear and overwrite the first one's code. The
    other arms do not share anything and can run in parallel with it."""
    GRAF_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(GRAF_LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _run_graflang(spec, model, run_dir)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _run_graflang(spec: str, model: str, run_dir: Path) -> ArmResult:
    shared = GRAPH.parent / ".grafr" / "logs"          # where the procedures write their artifacts (one folder for every run)
    for sub in ("spec", "target", "tests"):
        shutil.rmtree(shared / sub, ignore_errors=True)
    start = time.time()
    cmd = [sys.executable, "-m", "graphlang", "run", str(GRAPH), "--llm", f"{ADAPTER}:{model}",
           "--log-dir", str(run_dir / "logs"), "--log-format", "jsonl", "--output-dir", str(run_dir / "graf_out"), "--save-nodes",
           "--log-prompts", str(run_dir / "prompts"),
           "--param", f"spec={spec}", "--param", "check_closure=false"]
    try:
        done = _run(cmd, run_dir)
    except subprocess.TimeoutExpired:
        return ArmResult(seconds=time.time() - start, status="error:timeout")
    code = _read(shared / "target" / "python" / "code.py")
    for sub in ("spec", "target", "tests"):
        if (shared / sub).is_dir():
            shutil.copytree(shared / sub, run_dir / "artifacts" / sub, dirs_exist_ok=True)
    _save(run_dir, code)
    status, seconds = _finish(done, code, start)
    (run_dir / "stdout.txt").write_text(done.stdout + "\n--- stderr ---\n" + done.stderr, encoding="utf-8")
    verdict = _verdict(_read(shared / "tests" / "python" / "result.md"))
    cycles = _graf_cycles(run_dir, verdict, code)
    lines = [line for p in (run_dir / "logs").glob("spl-*.jsonl") for line in p.read_text(encoding="utf-8", errors="replace").splitlines()]
    return ArmResult(code=code, seconds=seconds, status=status, cycles=len(cycles), cycles_detail=cycles,
                     pipeline_verdict=verdict, llm=_spl_totals(lines, skip="code_pipeline"))


ARMS = {"single": run_single, "spl": run_spl, "graflang": run_graflang, "langgraph": run_langgraph}
