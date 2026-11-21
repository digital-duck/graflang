"""What the writer of one task needs to see (Python, run by a SOLVE node with backend: subprocess).

stdin   {"plan": the plan (JSON text), "task_index": 0-based task number, "files": {path: text} written so far, or empty}
stdout  one line of JSON: {"task": Markdown of the task, "title", "summary": the plan's summary, "first_file", "project": the files so far as text, "last": bool}

The project text lists every file written so far (`=== FILE: path ===` and its content), the newest last; when it is longer than the budget the oldest
files are shortened to their first lines, so a long project still fits in one prompt.
"""
import json
import re
import sys

BUDGET = 60_000


def parse(text):
    if isinstance(text, dict):
        return text
    text = (text or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fenced:
            return json.loads(fenced.group(1).strip())
        return json.loads(text[text.find("{"):text.rfind("}") + 1])


def project_text(files):
    if not isinstance(files, dict) or not files:
        return "(nothing written yet)"
    blocks = [(path, text) for path, text in files.items()]
    out = [f"=== FILE: {p} ===\n{t.rstrip()}\n" for p, t in blocks]
    total = sum(map(len, out))
    for i in range(len(out)):                                   # oldest first: cut them down to a head until the whole fits
        if total <= BUDGET:
            break
        path, text = blocks[i]
        head = "\n".join(text.splitlines()[:12])
        short = f"=== FILE: {path} (shortened) ===\n{head}\n...\n"
        total -= len(out[i]) - len(short)
        out[i] = short
    return "\n".join(out)


def main():
    data = json.load(sys.stdin)
    plan = parse(data.get("plan"))
    tasks = plan["tasks"]
    i = int(data.get("task_index") or 0)
    t = tasks[i]
    lines = [f"Task {t.get('id', i + 1)} of {len(tasks)}: {t.get('title', '')}", "", str(t.get("description", "")).strip(), "",
             "Files to write: " + ", ".join(t.get("files") or []), "", "Acceptance: " + str(t.get("acceptance", "")).strip()]
    if t.get("depends_on"):
        lines.append("Builds on: " + ", ".join(map(str, t["depends_on"])))
    print(json.dumps({"task": "\n".join(lines), "title": t.get("title", ""), "summary": plan.get("summary", ""),
                      "project": project_text(data.get("files")), "first_file": (t.get("files") or [""])[0], "last": i == len(tasks) - 1}))


if __name__ == "__main__":
    main()
