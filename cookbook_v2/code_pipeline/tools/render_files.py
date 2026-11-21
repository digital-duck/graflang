"""A project as text (Python, run by a SOLVE node with backend: subprocess).

stdin   {"files": {path: text}}
stdout  one line of JSON: {"text": every file as `=== FILE: path ===` and its content}
"""
import json
import sys

files = (json.load(sys.stdin).get("files") or {})
print(json.dumps({"text": "\n".join(f"=== FILE: {p} ===\n{t.rstrip()}\n" for p, t in sorted(files.items()))}))
