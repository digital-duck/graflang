import json
import sys

args = json.load(sys.stdin)
state = args.get("state")
if isinstance(state, str):
    state = json.loads(state)
line = "%s: %s" % (args.get("ticker", ""), str(args.get("insight", "")).strip())
state["remaining"] = state.get("remaining", [])[1:]
state["lines"] = state.get("lines", []) + [line]
print(json.dumps(state))
