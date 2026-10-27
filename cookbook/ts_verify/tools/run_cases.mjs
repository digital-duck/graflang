// Run the generated function against the test cases, in a child Node process that may read only the candidate and the runner:
// no file writes and no child processes (Node's permission model). Network and CPU are not restricted.
// stdin:  {"code": text, "function": name, "cases": JSON text [{"args": [...], "expected": ...}] or a path to a JSON file, "timeout_ms": optional}
// stdout: {"ok": bool, "passed": n, "total": n, "failed": [{"args", "expected", "actual" | "error"}]} or {"ok": false, "error": text}
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { extractCode, fail, print, readInput } from "./common.mjs";

const input = readInput();
const here = dirname(fileURLToPath(import.meta.url));
const name = String(input.function ?? "");
if (!/^[A-Za-z_$][\w$]*$/.test(name)) fail(`"function" must be a JavaScript identifier, got ${JSON.stringify(input.function)}`);

let cases;
try {
  const text = String(input.cases ?? "").trim();
  cases = JSON.parse(text.startsWith("[") ? text : readFileSync(text, "utf8"));  // a relative path starts in the graph's folder
  if (!Array.isArray(cases) || !cases.every((c) => Array.isArray(c.args) && "expected" in c)) throw new Error('want a list of {"args": [...], "expected": ...}');
} catch (e) {
  fail(`cannot read the test cases: ${e.message}`);
}

const limit = Number(input.timeout_ms ?? 10_000);   // the child is killed after this many milliseconds

const dir = mkdtempSync(join(tmpdir(), "ts-verify-"));
try {
  const candidate = join(dir, "candidate.ts");
  writeFileSync(candidate, extractCode(input.code));
  const run = spawnSync(
    process.execPath,
    ["--permission", `--allow-fs-read=${dir}`, `--allow-fs-read=${here}`, join(here, "case_runner.ts"), candidate, name],
    { input: JSON.stringify(cases), encoding: "utf8", timeout: limit, maxBuffer: 1 << 20 },
  );
  const lastLine = (run.stdout ?? "").trim().split("\n").pop();
  if (run.error?.code === "ETIMEDOUT") print({ ok: false, error: `timed out after ${limit / 1000} s (an endless loop?)` });
  else if (lastLine?.startsWith("{")) print(JSON.parse(lastLine));
  else print({ ok: false, error: (run.stderr ?? "").trim().split("\n").filter((l) => !l.includes("ExperimentalWarning")).slice(-3).join(" | ") || `exit ${run.status}` });
} finally {
  rmSync(dir, { recursive: true, force: true });
}
