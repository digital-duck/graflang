"""Put the run's result together (Python, run by a SOLVE node with backend: subprocess).

stdin   {"code": the last attempt (maybe fenced), "passed": bool, "type_report": JSON text or null,
         "case_report": JSON text or null, "attempts": [every attempt's code]}
stdout  one line of JSON: {"passed", "attempts": n, "code": clean code, "report": Markdown}
"""
import json
import re
import sys


def clean(code):
    fenced = re.search(r"```[a-zA-Z]*\n([\s\S]*?)```", code or "")
    return ((fenced.group(1) if fenced else code or "").strip()) + "\n"


def load(text):
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def main():
    data = json.load(sys.stdin)
    passed, attempts = bool(data.get("passed")), len(data.get("attempts") or [])
    types, cases = load(data.get("type_report")), load(data.get("case_report"))
    lines = ["## ts_verify", "", f"**Result:** {'PASSED' if passed else 'FAILED'} after {attempts} attempt(s)  "]
    if types is not None:
        lines.append("**Types:** " + ("not checked  " if not types.get("checked") else "clean  " if types.get("ok") else "errors  "))
    if cases is not None and "total" in cases:
        lines.append(f"**Cases:** {cases['passed']}/{cases['total']} passed  ")
    if not passed:
        lines.append("")
        for d in (types or {}).get("diagnostics", []):
            lines.append(f"- type error, {d}")
        if cases is not None and cases.get("error"):
            lines.append(f"- {cases['error']}")
        for f in (cases or {}).get("failed", []):
            lines.append(f"- f({', '.join(json.dumps(a) for a in f['args'])}) expected {json.dumps(f['expected'])}, "
                         + (f"got {json.dumps(f['actual'])}" if "actual" in f else f"raised {f['error']}"))
    print(json.dumps({"passed": passed, "attempts": attempts, "code": clean(data.get("code")), "report": "\n".join(lines)}))


if __name__ == "__main__":
    main()
