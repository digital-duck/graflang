"""Check a build plan (Python, run by a SOLVE node with backend: subprocess).

stdin   {"plan": the planner's reply (JSON, or JSON in a code fence), "lang": "python"}
stdout  one line of JSON: {"ok": bool, "report": text, "tasks": N}

A plan is {"ready": bool, "summary": text, "assumptions": [..], "deliverables": [{"name", "mechanism", "quality_bar"}], "tasks": [{"id", "title", "description", "files": [paths], "depends_on": [ids], "acceptance"}]}.
The check is the planner's feedback: a plan that is not specific enough to build from is returned with the list of what is missing, and the planner is asked again.
"""
import json
import posixpath
import re
import sys

MAX_TASKS, MAX_FILES, MIN_DESCRIPTION = 12, 5, 40


def parse(text):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fenced:
            try:
                return json.loads(fenced.group(1).strip())
            except ValueError:
                return None
        start, end = text.find("{"), text.rfind("}")           # JSON with a sentence before or after it
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                return None
    return None


def safe(path):
    path = posixpath.normpath(str(path).strip().replace("\\", "/"))
    return bool(path) and path != "." and not path.startswith(("/", ".."))


def check(plan, lang):
    if not isinstance(plan, dict):
        return ["the reply is not a JSON object: reply with the JSON plan only"]
    problems = []
    if plan.get("ready") is not True:
        missing = plan.get("missing") or plan.get("questions") or []
        problems.append("the planner says the specification cannot be planned yet" + (f"; it asks: {'; '.join(map(str, missing))}" if missing else "")
                        + ". State your assumptions in `assumptions` and plan anyway, setting ready=true, unless the specification is truly unusable")
    if not str(plan.get("summary") or "").strip():
        problems.append("`summary` is missing: one paragraph on what is built and how it is laid out")
    deliverables = plan.get("deliverables")
    if not isinstance(deliverables, list) or not deliverables:
        problems.append("`deliverables` is missing: list what the specification asks the product to produce, each with its `mechanism` and `quality_bar`")
    else:
        for n, d in enumerate(deliverables, 1):
            if not isinstance(d, dict) or not all(str(d.get(k) or "").strip() for k in ("name", "mechanism", "quality_bar")):
                problems.append(f"deliverable {n} needs a `name`, a `mechanism` (how its content is produced) and a `quality_bar` (what makes it good, not merely present)")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return problems + ["`tasks` must be a non-empty list"]
    if len(tasks) > MAX_TASKS:
        problems.append(f"{len(tasks)} tasks is too many (at most {MAX_TASKS}): merge small ones")
    seen_ids, owner = [], {}
    has_test = False
    for n, t in enumerate(tasks, 1):
        if not isinstance(t, dict):
            problems.append(f"task {n} is not an object")
            continue
        tid = str(t.get("id") or "").strip()
        where = f"task {tid or n}"
        if not tid:
            problems.append(f"task {n} has no `id`")
        elif tid in seen_ids:
            problems.append(f"{where}: the id is used twice")
        if not str(t.get("title") or "").strip():
            problems.append(f"{where}: `title` is missing")
        if len(str(t.get("description") or "").strip()) < MIN_DESCRIPTION:
            problems.append(f"{where}: `description` is too thin to build from (say what to implement: the public functions or classes, their signatures and behaviour)")
        if not str(t.get("acceptance") or "").strip():
            problems.append(f"{where}: `acceptance` is missing (how do we know it works? name the tests)")
        files = t.get("files")
        if not isinstance(files, list) or not files:
            problems.append(f"{where}: `files` must list the files this task writes")
            files = []
        if len(files) > MAX_FILES:
            problems.append(f"{where}: {len(files)} files is too many for one task (at most {MAX_FILES}): split it")
        for f in files:
            if not safe(f):
                problems.append(f"{where}: {f!r} is not a safe relative path")
            elif posixpath.normpath(f) in owner:
                problems.append(f"{where}: {f} is also written by task {owner[posixpath.normpath(f)]}: give each file to one task")
            else:
                owner[posixpath.normpath(f)] = tid or n
            base = posixpath.basename(str(f))
            has_test = has_test or base.startswith("test_") or base.endswith("_test.py") or "/tests/" in "/" + str(f)
        for d in t.get("depends_on") or []:
            if d not in seen_ids:
                problems.append(f"{where}: depends_on {d!r}, which is not an earlier task (order the tasks so each only depends on earlier ones)")
        seen_ids.append(tid)
    if lang.lower() == "python" and not has_test:
        problems.append("no task writes a test file (tests/test_*.py): the build is checked by running the project's tests")
    return problems


def main():
    data = json.load(sys.stdin)
    plan = parse(data.get("plan"))
    problems = check(plan, data.get("lang") or "python")
    n = len(plan["tasks"]) if isinstance(plan, dict) and isinstance(plan.get("tasks"), list) else 0
    if problems:
        report = "The plan is not good enough yet:\n" + "\n".join(f"- {p}" for p in problems)
    else:
        report = f"[READY] {n} tasks"
    print(json.dumps({"ok": not problems, "report": report, "tasks": n}))


if __name__ == "__main__":
    main()
