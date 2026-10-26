"""The deterministic compliance check, run by the graph as a program (a SOLVE with `backend: subprocess`).

stdin   one JSON object: {"pii_map": the model's reply as text, "destination": ..., "engine": stdlib|sympy|z3,
        "rules_file": path to your rules JSON, or "" for rules.json next to this file}
stdout  one line of JSON, the verdict: {"status": "OK", "engine", "compliant", "violated": [rule ids], "facts": {...}}
exit    0 when the check ran (a violation is a result, not a failure); 1 when it could not run (an unknown engine, a
        missing solver package, a bad rules file), with the reason on stderr. The run then stops and nothing is released.

A reply that is not a readable PII map is not "no PII": it gives compliant=false and the violation UNREADABLE_PII_MAP.

Try it:  echo '{"pii_map": "{\"entities\": [{\"type\": \"SSN\"}]}", "destination": "external_api", "engine": "stdlib"}' \
             | python procedures/compliance_check.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # `python -I` does not put the script's folder on the path
import tools  # noqa: E402


def fail(reason: str) -> int:
    print(f"compliance check could not run: {reason}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        inputs = json.load(sys.stdin)
    except ValueError as e:
        return fail(f"stdin is not JSON: {e}")
    try:
        rules = tools.load_rules_file(inputs.get("rules_file", ""))
    except ValueError as e:                                   # a mistake in your rules is shown, never replaced by the defaults
        return fail(str(e))
    verdict = tools.check_pii_map(tools.parse_pii_map_text(inputs.get("pii_map", "")), inputs.get("destination", ""),
                                  tools.normalize_engine(inputs.get("engine", "")), rules)
    if verdict.get("status") != "OK":
        return fail(verdict.get("error", "unknown error"))
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())
