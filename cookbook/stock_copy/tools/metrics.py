import json
import sys


def compute_metrics(csv_data):
    if csv_data.startswith("error:"):
        return "error: empty data"
    closes = []
    for row in csv_data.splitlines()[1:]:
        parts = row.split(",")
        if len(parts) == 2:
            try:
                closes.append(float(parts[1]))
            except ValueError:
                pass
    if not closes:
        return "error: empty data"
    start, end = closes[0], closes[-1]
    change = (end - start) / start * 100 if start else 0.0
    return ("start=%.2f, end=%.2f, high=%.2f, low=%.2f, change=%.2f%%, average=%.2f, days=%d"
            % (start, end, max(closes), min(closes), change, sum(closes) / len(closes), len(closes)))


args = json.load(sys.stdin)
data = args.get("data")
if isinstance(data, str):
    data = json.loads(data)
print(json.dumps({"ticker": data.get("ticker", ""), "text": compute_metrics(data.get("csv", ""))}))
