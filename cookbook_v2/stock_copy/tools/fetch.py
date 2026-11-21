import json
import sys
import urllib.request
from datetime import datetime, timezone


def fetch_ohlcv(ticker, days):
    try:
        url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%dd&interval=1d"
               % (ticker, int(days)))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        rows = ["date,close"]
        for ts, close in zip(stamps, closes):
            if close is None:
                continue
            day = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
            rows.append("%s,%.4f" % (day, close))
        if len(rows) == 1:
            return "error: no data for " + ticker
        return "\n".join(rows)
    except Exception as exc:
        return "error: %s" % exc


args = json.load(sys.stdin)
state = args.get("state")
if isinstance(state, str):
    state = json.loads(state)
remaining = state.get("remaining", [])
if not remaining:
    print(json.dumps({"ticker": "", "csv": "error: no ticker left"}))
else:
    ticker = remaining[0]
    print(json.dumps({"ticker": ticker, "csv": fetch_ohlcv(ticker, args.get("days", 30))}))
