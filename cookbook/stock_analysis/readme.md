# stock_analysis

Fetch the recent prices of a few tickers, compute simple metrics, have a model comment on each ticker, then have it write one portfolio outlook. It is the "use Python for what Python can test, the model only for reasoning" pattern: the data steps are `SOLVE` nodes that run Python in graflang's kernel, the two model steps are `GENERATE` nodes. Lifted from SPL.py's `cookbook/066_stock_analysis` by `spl2graph`, then reworked by hand (see *What changed in the lift*).

```
wf_entry -> split -> each_ticker (BATCH: fetch -> metrics -> interpret -> line) -> join_lines -> synthesize -> wf_exit
```

| | |
|---|---|
| Input | `tickers` (TEXT, comma separated, default `AAPL,META,GOOG,CRM`), `days` (INT, default `30`) |
| Output | `report` (TEXT): the portfolio outlook |
| LLM calls | one per ticker plus one: 5 with the default tickers |
| Needs | the `kernel` extra (`pip install -e ".[kernel]"`), network access to Yahoo Finance (no API key), `claude_cli` or another LLM |

## Run

```bash
graf run cookbook/stock_analysis/stock_analysis.graph.yaml --param tickers="AAPL,MSFT" --param days=30 --bind cookbook/stock_analysis/stock_analysis.bind.yaml
```

`stock_analysis.bind.yaml` caps the run (`limits: {max_llm_calls: 6, ...}`): the recipe makes one call per ticker plus one, so a long `tickers` list is a long bill and needs a higher cap. `graf run` uses `claude_cli` with `claude-sonnet-5-5` unless you pass `--llm adapter:model`.

## What the steps do

| Node | Type | |
|---|---|---|
| `split` | `SOLVE` (kernel) | turns `AAPL, MSFT` into the JSON list `["AAPL", "MSFT"]` |
| `each_ticker` | `BATCH` | runs its body once per ticker (`item_var: ticker`), in order, and collects one `line` per ticker |
| `fetch` | `SOLVE` (kernel) | downloads the daily closes from Yahoo Finance as `date,close` CSV; on a failure the text starts with `error:` |
| `metrics` | `SOLVE` (kernel) | start, end, high, low, change in percent, average, number of days |
| `interpret` | `GENERATE` | two sentences per ticker: the trend and one risk or opportunity |
| `line` | `CONTEXT` | `AAPL: <the two sentences>` |
| `join_lines` | `SOLVE` (kernel) | the lines, one paragraph each |
| `synthesize` | `GENERATE` | the portfolio outlook: best and worst performer, correlated risk, one recommendation |

## What changed in the lift

`spl2graph` wrote this graph with a `LOOP` whose condition was `@in_ticker IN @in_tickers`. A `LOOP` here repeats while a condition holds and has no list to walk, so the run stopped at once: `unknown variable @in_ticker`. The per-ticker steps are now a `BATCH` over the list of tickers, which is what the SPL `WHILE @ticker IN @tickers` meant. Also:

- the `split` and `join_lines` nodes do in Python what SPL's list iteration and `@report + @ticker + ': ' + ...` did;
- the empty `set_1` and the `set_3` that only copied the answer are gone;
- the `synthesize` prompt now includes `{{in_days}}` (the SPL prompt asked for the time frame but was never given it);
- SPL's `EXCEPTION WHEN BudgetExceeded THEN RETURN @report` has no counterpart: when the budget in `--bind` is hit the run fails with the reason and returns no partial report.

## Things to check

- The prices come from Yahoo Finance's public chart endpoint, which can change or refuse a request. If a ticker is unknown or the network is down, `fetch` returns `error: ...`; `metrics` turns it into `error: empty data` and the model is then asked to comment on that text. Check the `metrics` value of each ticker before you trust a comment.
- The `code` of the kernel nodes runs on your computer, and the app (`graf vis --edit`) asks you to confirm before it runs a graph that contains programs. `fetch` uses `datetime.utcnow()`, which newer Pythons mark as deprecated (a warning, not an error).
- This is a demonstration of the pattern, not investment advice: two sentences from a model about a few days of closing prices.


## Roundtrip Experiment

```bash

graf describe cookbook/stock_analysis --llm

graf create --name stock_copy --spec @cookbook/stock_analysis/stock_analysis.spec.md --allow-code

mv stock_copy cookbook

graf run cookbook/stock_copy/stock_copy.graph.yaml 

```

### Output

```
Output: {'report': "Over the last 30 days, the AAPL, META, GOOG, CRM portfolio has leaned bearish, with AAPL the lone gainer (+1.67% to 
344.63, just below its 348.91 high) and GOOG the weakest performer (-20.71% to 278.22, closing at its period low), followed closely by 
META (-17.03%, near its 612.49 low). Three of the four names are trading below their 30-day averages, and the sharp, simultaneous declines
in GOOG and META point to correlated risk in large-cap tech and growth exposure, while CRM's mild slide (-3.07%) sits only about 2% above 
its 224.56 low and adds to the downside pressure. AAPL's resistance at 348.91 is the key near-term test for the portfolio's only positive 
contributor. Recommendation: hold AAPL, avoid adding to GOOG and META until they stabilize above their recent lows, and set a stop near 
CRM's 224.56 low to limit further drawdown."}

31 steps · 5 LLM calls, 901 tokens in / 573 out · slowest: each_ticker 19.5s

output: /home/gongai/projects/digital-duck/graflang/cookbook/stock_copy/output/stock_copy-claude_cli-claude-sonnet-5-5-20261101-093021
log: /home/gongai/.graflang/logs/stock_copy-claude_cli-claude-sonnet-5-5-20261101-093021.log
```