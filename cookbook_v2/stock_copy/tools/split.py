import json
import sys

args = json.load(sys.stdin)
items = [t.strip() for t in str(args.get("tickers", "")).split(",") if t.strip()]
print(json.dumps({"remaining": items, "lines": [], "count": len(items)}))
