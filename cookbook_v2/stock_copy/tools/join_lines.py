import json
import sys

args = json.load(sys.stdin)
state = args.get("state")
if isinstance(state, str):
    state = json.loads(state)
print(json.dumps({"text": "\n\n".join(state.get("lines", []))}))
