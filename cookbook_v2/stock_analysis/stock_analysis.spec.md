# stock_analysis

Fetch the recent prices of a few tickers, compute simple metrics, have a model comment on each ticker, then have it write one portfolio outlook. It is the "use Python for what Python can test, the model only for reasoning" pattern: the data steps are `SOLVE` nodes that run Python in graflang's kernel, the two model steps are `GENERATE` nodes. Lifted from SPL.py's `cookbook/066_stock_analysis` by `spl2graph`, then reworked by hand (see *What changed in the lift*).

## Inputs
- `tickers` (TEXT), default `AAPL,META,GOOG,CRM`
- `days` (INT), default `30`

## Output
- `report` (TEXT)

## What it does, step by step

1. **split** (SOLVE) computes with Python code: `_result = json.dumps([t.strip() for t in tickers.split(',') if t.strip()])`
   - reads: tickers (from the workflow's input)
2. **each_ticker** (BATCH) runs the steps below once for each item of its list (each one is `ticker`), in order
   - reads: items (from split's items), days (from the workflow's input)
   1. **fetch** (SOLVE) computes with Python `fetch_ohlcv(ticker, days)`: Fetch recent OHLCV data from Yahoo Finance (no API key needed).
   2. **metrics** (SOLVE) computes with Python `compute_metrics(csv_data)`: Compute simple price metrics from date,close CSV.
      - reads: raw_data (from fetch's raw_data)
   3. **interpret** (GENERATE) asks the model (`interpret_metrics`):
      > You are a financial analyst. Given the following price metrics for {{in_ticker}},
      > write a concise two-sentence summary covering:
      >   1. Overall trend direction (bullish / bearish / sideways).
      >   2. One key risk or opportunity based on the data.
      >
      > Metrics: {{in_metrics}}
      - reads: metrics (from metrics's metrics)
   4. **line** (CONTEXT) sets a value: `@in_ticker + ': ' + @in_insight`
      - reads: insight (from interpret's insight)
   - keeps: lines from line.out_line
3. **join_lines** (SOLVE) computes with Python code: `_result = '\n\n'.join(lines)`
   - reads: lines (from each_ticker's lines)
4. **synthesize** (GENERATE) asks the model:
   > You are a portfolio manager. Given the following per-stock summaries for {{in_tickers}}
   > over the last {{in_days}} days, produce a brief (3-5 sentence) consolidated portfolio outlook that:
   >   - opens with the tickers and time frame,
   >   - highlights the best and worst performers,
   >   - notes any correlated risk across the portfolio,
   >   - ends with a single actionable recommendation.
   >
   > Summaries:
   > {{in_summaries}}
   - reads: summaries (from join_lines's summaries), tickers (from the workflow's input), days (from the workflow's input)

## Notes
- Model steps: 2 (a step inside a repeat or a per-item run makes one call each time it runs).
- Program steps: 4; they run Python or another program on the computer that runs the graph.

## Files that come with the graph
- `readme.md`
- `stock_analysis.bind.yaml`
