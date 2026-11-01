# stock_analysis

## Purpose
Fetches recent daily prices for a few stock tickers, computes simple price metrics in Python, asks a model to comment briefly on each ticker, then asks it to write one consolidated portfolio outlook. It follows the pattern "use Python for what Python can test, the model only for reasoning". It is meant as a demonstration of that pattern, not as investment advice.

## Inputs
- `tickers` (TEXT, default `AAPL,META,GOOG,CRM`): comma-separated ticker symbols.
- `days` (INT, default `30`): how many recent days of prices to fetch and the time frame named in the outlook.

## Output
- `report` (TEXT): the portfolio outlook, a brief paragraph of 3-5 sentences written by the model.

## How it works
1. **split** (program step, Python in a kernel). Turns the `tickers` text into a JSON list of trimmed, non-empty symbols. Code: `_result = json.dumps([t.strip() for t in tickers.split(',') if t.strip()])`. For example `AAPL, MSFT` becomes `["AAPL", "MSFT"]`.
2. **each_ticker** (per-item run). Runs the four sub-steps below once for each item of the list from `split`, in order, with the current item named `ticker`; `days` is passed in from the workflow input. It collects one `line` per ticker into a list called `lines`.
   1. **fetch** (program step). Calls `fetch_ohlcv(ticker, days)`, which downloads recent daily data from Yahoo Finance's public chart endpoint (no API key) and returns the daily closes as `date,close` CSV text. It uses `datetime.utcnow()`. On failure (unknown ticker, network down) it returns text starting with `error:`.
   2. **metrics** (program step). Calls `compute_metrics(csv_data)` on the fetched CSV and returns simple metrics: start, end, high, low, change in percent, average, and number of days. If the input is an `error:` text, the result is `error: empty data`.
   3. **interpret** (model step, prompt `interpret_metrics`). The instruction is:
      > You are a financial analyst. Given the following price metrics for {{in_ticker}},
      > write a concise two-sentence summary covering:
      >   1. Overall trend direction (bullish / bearish / sideways).
      >   2. One key risk or opportunity based on the data.
      >
      > Metrics: {{in_metrics}}

      `in_ticker` is the current ticker and `in_metrics` is the output of `metrics`. The result is called `insight`.
   4. **line** (sets a value). Builds `@in_ticker + ': ' + @in_insight`, for example `AAPL: <the two sentences>`, and keeps it as the line for this ticker.
3. **join_lines** (program step). Joins the lines into one text, one paragraph each: `_result = '\n\n'.join(lines)`.
4. **synthesize** (model step). The instruction is:
   > You are a portfolio manager. Given the following per-stock summaries for {{in_tickers}}
   > over the last {{in_days}} days, produce a brief (3-5 sentence) consolidated portfolio outlook that:
   >   - opens with the tickers and time frame,
   >   - highlights the best and worst performers,
   >   - notes any correlated risk across the portfolio,
   >   - ends with a single actionable recommendation.
   >
   > Summaries:
   > {{in_summaries}}

   `in_tickers` and `in_days` come from the workflow inputs, `in_summaries` from `join_lines`. Its answer is the `report`.

## Rules and limits
- A failed fetch is not an error that stops the run: `fetch` returns `error: ...`, `metrics` turns it into `error: empty data`, and the model is still asked to comment on that text. Users should check each ticker's metrics before trusting a comment.
- No retries, fallbacks or policies are defined.
- The run can be capped with a bound limits file (e.g. `limits: {max_llm_calls: 6}`). If the budget is hit, the run fails with the reason and returns no partial report.
- Needs network access to Yahoo Finance and a working model adapter.

## Programs
Yes, the app needs programs: four Python steps that run in a kernel (`split`, `fetch`, `metrics`, `join_lines`), so the builder must be told to allow them (`graf create --allow-code`). They need the `kernel` extra (jupyter_client, ipykernel) and network access for `fetch`. Functions used: `fetch_ohlcv(ticker, days)`, `compute_metrics(csv_data)`, plus the two one-line snippets above.

## Cost
One model call per ticker plus one for the outlook: 5 calls with the default four tickers (N + 1 for N tickers).

## Keep
- Inputs: `tickers`, `days`.
- Output: `report`.
- Step names: `split`, `each_ticker` (item name `ticker`, collected list `lines`), `fetch`, `metrics`, `interpret`, `line`, `join_lines`, `synthesize`.
- Prompt name: `interpret_metrics`.
- Placeholders: `in_ticker`, `in_metrics`, `in_tickers`, `in_days`, `in_summaries`.
