# stock_report

Writes a short market report from real data. A loop over the tickers fetches prices, computes metrics with plain programs and has the model write one insight line per ticker;
then one call turns the lines into the report.

```
stock_report    gather -> report
  gather/       split the ticker list, count it, then per ticker: fetch prices (tools/fetch.py), compute metrics (tools/metrics.py), one insight line (model)
  report/       join the lines, then one model call writes the report
```

Inputs: `tickers` (default `AAPL,META,GOOG,CRM`), `days` (default 30). Output: `report`. Model calls: one per ticker plus one. `tools/fetch.py` is the only step that uses the
network. The programs in `tools/` read JSON on stdin and write JSON; a command runs from this folder, so `tools/` stays beside the top graph.

```bash
graf run cookbook_v2/stock_report/stock_report.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 --param tickers="AAPL,MSFT" --param days=30
```

If the call limit is hit the run fails and returns no partial report. Original: `cookbook/stock_copy`; its readme has the data-source notes.
