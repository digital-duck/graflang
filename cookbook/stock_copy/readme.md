# stock_copy

Fetches recent daily prices for a few stock tickers, computes simple metrics in Python, asks a model to comment briefly on each ticker, then asks it to write one consolidated portfolio outlook. The pattern: Python for what Python can test, the model only for reasoning. A demonstration, not investment advice.

## Inputs
- `tickers` (TEXT, default `AAPL,META,GOOG,CRM`): comma-separated ticker symbols.
- `days` (INTEGER, default `30`): how many recent days of prices to fetch, and the time frame named in the outlook.

## Output
- `report` (TEXT): a portfolio outlook of 3-5 sentences.

## Run
```
graf run stock_copy.graph.yaml --param tickers="AAPL,MSFT" --param days=30
```
Cap the cost with a `--bind` file containing `limits: {max_llm_calls: 6}`. If the budget is hit, the run fails and returns no partial report.

## How it works
1. `split` (program, `tools/split.py`): turns `tickers` into a list of trimmed, non-empty symbols; `count` reads how many.
2. `each_ticker` (loop, one round per ticker, in order), carrying a `state` with the tickers still to do and the lines so far:
   - `fetch` (`tools/fetch.py`): downloads daily closes from Yahoo Finance's public chart endpoint (no API key) as `date,close` CSV. On failure it returns text starting with `error:`.
   - `metrics` (`tools/metrics.py`): start, end, high, low, change in percent, average, number of days. An `error:` input becomes `error: empty data`.
   - `interpret` (model, prompt `interpret_metrics`): two sentences on trend and one risk or opportunity.
   - `line` (`tools/line.py`): builds `TICKER: <insight>` and moves on to the next ticker.
3. `join_lines` (`tools/join_lines.py`): joins the lines, one paragraph each.
4. `synthesize` (model, prompt `synthesize`): the portfolio outlook, which is the `report`.

## Notes
- A failed fetch does not stop the run: the model is still asked to comment on the `error: empty data` text. Check each ticker's metrics before trusting a comment.
- Needs network access to Yahoo Finance (for `fetch` only) and a working model adapter. The programs use only the Python 3 standard library.
- Differences from the specification: the per-ticker work is a `loop` rather than a per-item run, and the programs run as subprocess steps rather than in a kernel, so the `kernel` extra is not needed. Building it needs `--allow-code`.
- Cost: one model call per ticker plus one for the outlook, N + 1 calls (5 with the default four tickers).
