# Recipe 119 — Demand Forecasting (statsmodels Structural Time Series)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/119_demand_forecast` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 269 tokens in / 468 out in total); the model remarked that the forecast table in its prompt was empty; not investigated yet. A run that completes does not show the answer is right: read the output before you rely on a recipe.

Given a historical demand time series, decompose it into trend + seasonal + irregular components and forecast future periods — using statsmodels `UnobservedComponents` (Kalman filter / MLE). The ASSERT gate requires the model's hold-out RMSE to beat a naïve last-value baseline before the forecast is surfaced.

**DODA**: same `.spl` spec runs on any adapter. Production upgrade path: replace `statsmodels` with `PyMC` or `Prophet` by swapping the `fit_structural_ts` tool — zero `.spl` changes.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | statsmodels `UnobservedComponents` (local linear trend + seasonal) | LLM seasonal trend extrapolation |
| Guarantee | RMSE beats naïve baseline (ASSERT gate) | Sanity check only (±50% of last value) |
| Verification | Hold-out RMSE vs. naïve | `verify_forecast_off` gross bounds check |
| Solver class | Statistical state-space (Kalman filter, MLE) | — |

## Default problem

```
36 months of widget sales — clear upward trend (~7% YoY) + Q4 seasonal spike

Year 1: 95, 90, 102, 108, 112, 115, 118, 120, 115, 112, 135, 152
Year 2: 102, 97, 110, 116, 120, 124, 127, 129, 124, 121, 145, 164
Year 3: 109, 104, 118, 125, 129, 133, 137, 139, 133, 130, 156, 176

Forecast horizon: 6 months (configurable via --param periods=N)
```

**Plain English**: You have 3 years of monthly sales. The model decomposes them into a local linear trend (growing ~7% per year) and a seasonal pattern (Q4 spike, Q1 dip). It holds out the last 6 months for validation, fits on months 1–30, then forecasts months 31–36. If its RMSE on the hold-out beats "just repeat the last value" — the naïve baseline — the ASSERT passes and the forecast is trusted.

## Example output (2026-09-06, claude-sonnet-4-6)

### solver=ON (statsmodels UnobservedComponents)

Trained on months 1–30; hold-out months 31–36; forecast = months 37–42 (Year 4 Jan–Jun):

| Period | Forecast | Lower 95% | Upper 95% |
|---|---|---|---|
| +1 | 182.7 | 158.7 | 206.6 |
| +2 | 191.2 | 164.9 | 217.4 |
| +3 | 212.9 | 184.1 | 241.6 |
| +4 | 205.1 | 173.8 | 236.3 |
| +5 | 205.0 | 171.1 | 238.9 |
| +6 | 219.9 | 183.4 | 256.3 |

**Hold-out RMSE: 10.00 vs naïve baseline 19.76 ✓ beats naïve (49% error reduction)**

CI widens from ±24 at +1 to ±36 at +6 — correct structural uncertainty growth. Seasonal pulse at +3 and +6 signals a repeating ~3-month cycle within the 6-month horizon.

**LLM interpretation highlights:**
- Clear upward trend: +1 (183) → +6 (220), ~20% over the horizon
- Seasonal pulse at +3 and +6: build safety stock ahead of those months
- Minimum replenishment target ~215 units/cycle for trend-plus-buffer
- Near-term orders: tighter commitments; months +5/+6: flex capacity or supplier options

### solver=OFF (LLM heuristic extrapolation)

```
Forecast: [160, 152, 174, 167, 182, 187]
Trend: growing
Reasoning: "~10% YoY growth with Q4 spike and Q1 dip; applying seasonal index to Year 4 Jan–Jun"
Sanity check: PASS (all values positive, within ±50% of last observed value 176)
```

### Comparison

| | solver=ON | solver=OFF |
|---|---|---|
| Forecast range | 182.7 – 219.9 | 160 – 187 |
| +1 (Year 4 Jan) | 182.7 | 160 |
| +6 (Year 4 Jun) | 219.9 | 187 |
| Systematic gap | — | ~25–33 units lower per period |
| Trend direction | Upward ✓ | Upward ✓ |
| Seasonal pulse | +3 and +6 spike (structural) | +1 dip, gentle rise |
| 95% CI | Yes (widening from ±24 to ±36) | No — point forecast only |
| Validation | RMSE 10.00 < naïve 19.76 (formal gate) | Sanity bounds only |
| LLM calls | 2 | 1 |
| Tokens in/out | 344 / 337 | 143 / 66 |
| Latency | 28s | 18s |

**Why the forecasts diverge:**

- **Direction**: both models agree — upward trend with seasonal variation. The LLM's qualitative reasoning is correct.
- **Magnitude**: the LLM claims ~10% YoY growth but its forecasts are ~40–50% above Year 3 Jan–Jun values (109–133), inconsistent with its own stated growth rate. The structural model's aggressive extrapolation reflects the trend slope estimated from months 1–30 plus the seasonal component projected forward.
- **Uncertainty**: only solver=ON provides calibrated confidence intervals. Without CI, solver=OFF cannot support inventory decisions that require safety stock calculations (e.g., "order enough to cover demand at 90% service level").
- **Seasonal decomposition**: solver=ON uses an explicit state-space seasonal component (Kalman filter); solver=OFF applies a single annual seasonal index mentally derived from the series description. The two seasonal patterns visibly differ — solver=ON shows a ~3-month within-horizon cycle; solver=OFF shows a monotonic rise after a January dip.

**Pattern vs. r117 (stochastic programming):** In r117, solver=OFF matched solver=ON exactly on every number because the problem had 3 discrete scenarios that the LLM could enumerate by hand. r119 shows the opposite: with a continuous time series and a 6-step forecast horizon, the LLM's heuristic diverges materially from the structural model — both in magnitude and in the shape of the seasonal pattern. The CI gap is particularly consequential: inventory decisions based on solver=OFF forecasts have no principled basis for safety stock sizing.

## Run commands

```bash
conda activate spl123
pip install statsmodels

# solver=ON — statsmodels UnobservedComponents (default 6 periods)
graf run cookbook_solvers/demand_forecast/demand_forecast.graph.yaml \
  --llm claude_cli \
  --param use_solver=true

# solver=OFF — LLM heuristic extrapolation
graf run cookbook_solvers/demand_forecast/demand_forecast.graph.yaml \
  --llm claude_cli \
  --param use_solver=false

# Custom forecast horizon
graf run cookbook_solvers/demand_forecast/demand_forecast.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param periods=12

# Custom problem (provide your own description — LLM will parse it)
graf run cookbook_solvers/demand_forecast/demand_forecast.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param problem="Quarterly retail sales: Q1=320, Q2=410, Q3=390, Q4=520, Q1=340, Q2=430, Q3=415, Q4=550"
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_problem()` | Return the default 36-month widget sales JSON |
| `fit_structural_ts(problem_json, periods)` | statsmodels UC fit + forecast → JSON |
| `is_forecast_valid(forecast_json)` | ASSERT gate: status==OK and RMSE beats naïve |
| `format_forecast_table(forecast_json)` | Forecast → markdown table with CI |
| `verify_forecast_off(problem_json, forecast_json)` | Sanity bounds check for solver=OFF |

## Model formulation

```
UnobservedComponents (local linear trend + seasonal):

  y_t = μ_t + γ_t + ε_t          (observation equation)

  μ_t = μ_{t-1} + ν_{t-1} + η_t  (level — random walk with drift)
  ν_t = ν_{t-1} + ζ_t             (trend/slope)
  γ_t = −∑_{j=1}^{s-1} γ_{t-j} + ω_t   (seasonal, s=12 for monthly)

Parameters estimated by MLE via Kalman filter.
```

## Production upgrade path

Replace `statsmodels` with a Bayesian solver without changing the `.spl` workflow:

| Stage | Recipe demo | Production |
|---|---|---|
| Fitting | `statsmodels` UnobservedComponents (MLE) | `PyMC` full Bayesian MCMC posterior |
| Seasonality | Fixed sinusoidal | `Prophet` auto-seasonality + holidays |
| Uncertainty | Asymptotic 95% CI | Full posterior predictive interval |

## Related recipes

- Recipe 99: Portfolio optimization (cvxpy — mean-variance)
- Recipe 108: Robust Supply Chain MILP (demand uncertainty via scenario tree)
- Recipe 117: Two-Stage Stochastic Programming (newsvendor under demand uncertainty)
- Recipe 100: Supply Sourcing Pareto front (multi-objective, PuLP)
