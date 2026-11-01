# Recipe 99 — Portfolio Optimization

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/099_portfolio_opt` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> The SPL file holds two workflows, so there are two graphs: `portfolio_optimization.graph.yaml` and `portfolio_comparison.graph.yaml` (`--main`/`--workflow` are gone from the commands: the graph you run is the workflow).
> Not ported: `readme-cvxpy-Markowitz.md`, `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): `portfolio_comparison` runs; `portfolio_optimization` needs live prices (yfinance). This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Personal use**: run monthly with fresh data for rebalancing signals.  
**DODA**: same `.spl` spec runs on any adapter — ollama for exploration, claude_cli for production.

---

## Chapter 1 — Portfolio Optimization with Markowitz

### The Problem

Given a pool of stock candidates and a capital amount, find the allocation that **minimizes risk while achieving a target annual return**. Risk is measured as portfolio variance — how much returns fluctuate — not just the risk of individual stocks in isolation.

### Why Diversification Has Math

The key insight of Harry Markowitz (1952): combining assets whose prices don't move in lockstep reduces overall portfolio risk. Two stocks that partially offset each other carry *less* combined risk than either alone, even if both are individually risky. This is the mathematical basis for diversification.

### The Optimization Formulation

```
Minimize    wᵀ Σ w                (portfolio variance — the risk)

Subject to  μᵀ w ≥ target_return  (must hit the return target)
            Σ wᵢ = 1              (fully invested — 100% deployed)
            wᵢ ≥ 0                (long only — no short selling)
            wᵢ ≤ max_weight       (position limit, e.g. 25%)
```

where `μ` = vector of annualized historical returns, `Σ` = annualized covariance matrix.

This is a **convex Quadratic Program (QP)** — the objective is quadratic, constraints are linear. Convexity guarantees a unique global optimum. Solved here via `cvxpy` with the CLARABEL interior-point solver.

### Inputs: What the Solver Needs

`fetch_stock_data` builds μ and Σ from historical daily prices via yfinance:

```
μᵢ     = mean(daily_returnsᵢ) × 252      (annualized mean return)
Σᵢⱼ    = cov(daily_returnsᵢ, dailyⱼ) × 252  (annualized covariance)
```

Off-diagonal Σᵢⱼ captures correlation: high → stocks move together (less diversification); low or negative → they offset (more diversification).

### Output Metrics

| Metric | Formula | Meaning |
|---|---|---|
| Expected return | `μᵀ w` | Annualized portfolio return |
| Volatility | `√(wᵀ Σ w)` | Annualized standard deviation |
| Sharpe ratio | `(return − Rf) / volatility` | Return per unit of risk |

Sharpe ratio is the headline quality metric. Higher is better; >1.0 is good, >2.0 is excellent.

### Constraints and Practical Limits

| Parameter | Default | Rationale |
|---|---|---|
| `min_tickers` | 5 | Hard floor enforced in solver; fewer stocks → insufficient diversification |
| `max_weight` | 0.25 | No single stock >25%; with 5 stocks this fills 100% exactly |
| `target_return` | 0.12 | 12% annual; if infeasible the LLM suggests a relaxed target |

### Run — Classic Markowitz

```bash
# solver=ON, Markowitz — live data + deterministic optimization
graf run ~/.graflang/solvers/portfolio_opt/portfolio_optimization.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param algorithm=markowitz \
  --param tickers="AAPL,MSFT,GOOGL,AMZN,NVDA,GDX,SILJ,WEAT,DBA,XLE" \
  --param capital=100000 \
  --param period=1y \
  --param target_return=0.12 \
  --param max_weight=0.20

# LLM calls: 1  Latency: 32535ms
# Log:     ./logs/portfolio_opt-claude_cli-claude-sonnet-4-6-20260903-204126.md


# solver=OFF — LLM heuristic allocation (back-checked by verify_portfolio)
graf run ~/.graflang/solvers/portfolio_opt/portfolio_optimization.graph.yaml \
  --llm claude_cli \
  --param use_solver=false \
  --param algorithm=markowitz \
  --param tickers="AAPL,MSFT,GOOGL,AMZN,NVDA,GDX,SILJ,WEAT,DBA,XLE" \
  --param capital=100000 \
  --param period=1y \
  --param target_return=0.12 \
  --param max_weight=0.20


```

### TOOL_API Reference

| Function | Purpose |
|---|---|
| `fetch_stock_data(tickers, period)` | yfinance → annualized μ + Σ |
| `optimize_portfolio(data, target_return, max_weight)` | cvxpy Markowitz QP |
| `optimize_by_algorithm(data, algorithm, target_return, max_weight)` | Dispatcher for all 6 algorithms |
| `allocate_capital(optimization_json, capital)` | Weights → dollar amounts |
| `verify_portfolio(optimization_json)` | Sanity checks: sum=1, bounds, non-negative return |

### Verification (solver=OFF path)

`verify_portfolio` back-checks the LLM's heuristic allocation:
1. **Budget**: weights sum ≈ 1.0 (within 2%)
2. **Long-only**: no negative weights
3. **Position limit**: no weight exceeds `max_weight`
4. **Sanity**: expected return and volatility are non-negative

### Deep Dive

See [readme-cvxpy-Markowitz.md](readme-cvxpy-Markowitz.md) for: full math derivation, cvxpy tutorial with code examples, and a comparison of all 6 algorithms including Black-Litterman, Risk Parity, HRP, and CVaR.

---

## Chapter 2 — AI-Powered Synthesis for Optimal Outcome

### The Limitation of Any Single Algorithm

No single optimization algorithm is universally best. The right choice depends on:

- **Data length**: short history (<1yr) → Markowitz over-fits; HRP is more robust
- **Number of stocks**: small N (<8) → covariance matrix is unstable; HRP avoids inversion
- **Investor objective**: minimize tail loss → CVaR; maximize risk-adjusted return → Max Sharpe
- **Return predictability**: noisy μ estimates → Min Variance (ignores return target entirely)
- **Asset type mix**: multi-asset (stocks + bonds + commodities) → Risk Parity

Choosing manually requires deep quant knowledge. This is precisely where LLM synthesis adds value.

### The 6 Algorithms Available

| Algorithm | Key idea | Best when |
|---|---|---|
| `markowitz` | Minimize variance subject to return target | History >2yr, N ≥ 10, trust μ estimates |
| `min_variance` | Minimize variance only, no return target | μ estimates are noisy; defensive mandate |
| `max_sharpe` | Maximize return per unit risk (Charnes-Cooper transform) | Single optimal portfolio on efficient frontier |
| `risk_parity` | Equal risk contribution from each asset | Multi-asset, diversified mandate, no return view |
| `hrp` | Hierarchical clustering + recursive bisection; no matrix inversion | Small N, short history, unstable correlations |
| `cvar` | Minimize expected loss in worst 5% of scenarios | Downside protection; fat-tailed return distributions |

### Parallelism Model

`CALL PARALLEL` dispatches branches via `asyncio.gather` — coroutine-level concurrency on a single event loop. For CPU-bound solvers like cvxpy and scipy, real parallelism comes from the Hub routing each branch to a different compute node. The `ON GRID` clause makes this explicit.

| Model | Mechanism | CPU parallelism | Best for |
|---|---|---|---|
| asyncio coroutines | Cooperative suspend/resume, one thread | No | I/O-bound: LLM API calls, yfinance fetches |
| Thread pool (`run_in_executor`) | OS threads, GIL applies | Partial — if C extensions release GIL | Mixed: cvxpy releases GIL, so threads help |
| Process pool | Separate Python interpreters | Yes | Pure CPU-bound Python code |
| Node dispatch (Hub / `ON GRID`) | Remote workers over network | Yes, fully independent | Any workload at cluster scale |

For the 6-algorithm sweep, `CALL PARALLEL ON GRID "momagrid"` routes each solver to a separate Momagrid node — true node-level parallelism, latency determined by the slowest algorithm rather than the sum of all six.

### Pattern 1 — LLM Selects the Algorithm (`algorithm=auto`)

Instead of hardcoding an algorithm, the workflow lets the LLM read the market data — number of tickers, history length, return spread, correlation structure — and recommend the most appropriate algorithm for *this specific input*.

```
[Deterministic]  fetch_stock_data   →  μ, Σ
[LLM]            suggest_algorithm  →  "hrp"          (reads data characteristics)
[Deterministic]  optimize_by_algorithm("hrp")  →  weights
[LLM]            interpret_portfolio  →  plain-English explanation
```

```bash
graf run ~/.graflang/solvers/portfolio_opt/portfolio_opt.graph.yaml \
  --adapter claude_cli \
  --param use_solver=true \
  --param algorithm=auto \
  --param tickers="MOS,EWZ,GLD,TLT,VNQ,XLE" \
  --param capital=15000 \
  --param target_return=0.10
```

The LLM acts as a **data-aware algorithm selector** — not a guesser, but a reasoner that reads the actual characteristics of the input before choosing a method.

### Pattern 2 — Cross-Algorithm Sweep + LLM Synthesis

The `portfolio_comparison` workflow runs **all 6 algorithms on the same data**, then uses one LLM call to synthesise the results, compare trade-offs, and recommend the best fit for the investor.

```
[Deterministic × 6]  optimize_by_algorithm × 6  →  6 result JSONs
[LLM × 1]           compare_algorithms          →  comparison table + recommendation
```

This is the **SPL synthesis pattern**: N independent deterministic computations feed a single LLM synthesis step that reasons holistically across all results. The math is exact; the synthesis is intelligent.

```bash
graf run ~/.graflang/solvers/portfolio_opt/portfolio_comparison.graph.yaml \
  --adapter claude_cli \
  --param tickers="AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,BRK-B" \
  --param capital=20000 \
  --param period=2y \
  --param target_return=0.15 \
  --param max_weight=0.25
```

The LLM synthesis output includes:
- Comparison table: algorithm | return | volatility | Sharpe | # positions
- Which algorithm gives the best risk-adjusted return
- Which gives the most diversified allocation
- A concrete recommendation with reasoning for *this specific portfolio*
- Flags for any algorithms that failed or produced degenerate weights

### Why This Matters — The Synthesis Value of SPL

In traditional code, the cross-algorithm comparison step requires custom ranking logic, hardcoded weights for "what better means," and manual formatting — easily 200+ lines that bake in the developer's assumptions. The LLM synthesis call does this holistically in one step, adapting its reasoning to the specific portfolio, period, and investor context provided.

The roles are cleanly separated:

| Role | Who does it | Guarantee |
|---|---|---|
| Data fetching | yfinance (deterministic) | Exact historical prices |
| Mathematical optimization | cvxpy / scipy (deterministic) | Provably optimal within constraints |
| Algorithm selection | LLM (`suggest_algorithm`) | Context-aware, adaptive |
| Result synthesis | LLM (`compare_algorithms`) | Holistic, investor-friendly |
| Correctness gate | `ASSERT is_optimized()` | Hard stop if solver fails |

This deterministic-probabilistic boundary — where each side does what it is best at — is the core architectural principle of SPL.

### Infeasibility Handling

If a target return is too aggressive for the stock universe, the workflow self-corrects:
1. Solver returns `INFEASIBLE`
2. LLM (`suggest_relaxed_target`) reads the historical returns and proposes an achievable target
3. Solver retries with the relaxed target
4. `ASSERT is_optimized()` gates on success — hard failure if still infeasible

This is the **deterministic–probabilistic boundary** made explicit: the LLM reasons about what's achievable; the solver enforces it mathematically.

### Adaptive Monthly Rebalancing

Run the comparison workflow monthly. Fresh μ and Σ mean the algorithm recommendation may change — e.g. HRP in volatile periods, Markowitz when markets are calm and history is long.

```bash
# Monthly rebalancing signal — let the data and LLM decide the method
graf run ~/.graflang/solvers/portfolio_opt/portfolio_comparison.graph.yaml \
  --llm claude_cli \
  --param tickers="AAPL,MSFT,GOOGL,AMZN,NVDA,GDX,SILJ,WEAT,DBA,XLE" \
  --param capital=100000 \
  --param period=1y \
  --param target_return=0.12 \
  --param max_weight=0.20

```

---

## Output Metadata

| Field | Value |
|---|---|
| `objective` | Sharpe ratio of the selected portfolio |
| `verify` | PASS / FAIL / N/A (solver=OFF path) |
| `status` | complete |

## Disclaimer

Past performance does not guarantee future results. This recipe is for educational  
and personal exploration purposes only — not financial advice.

## Related Recipes

- Recipe 78: LP / MILP via PuLP (linear & integer programs)
- Recipe 98: Job-shop scheduling via OR-Tools CP-SAT (constraint programming)
