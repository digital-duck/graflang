# Recipe 124 — Discrete-Event Simulation: Hospital Emergency Department (SimPy)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/124_simpy_des` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Solver class:** Discrete-Event Simulation (DES) — "what happens?" not "what is optimal?"  
**Backend:** SimPy  
**Dependency:** `pip install simpy`

## What it demonstrates

Every other solver recipe answers "what is **optimal**?" — minimize cost, maximize yield,
find Nash equilibrium. This recipe introduces a fundamentally different solver class:
**Discrete-Event Simulation (DES)**. DES answers "what **happens**?" under stochastic
dynamics. It produces *trajectories*, not solutions.

DES is not competing with LP/MILP/CP — it is **complementary**. The natural SPL pattern:
```
CALL simulate → CALL optimize  (understand the system, then improve it)
```

| | solver=ON (SimPy) | solver=OFF (M/M/c + LLM) |
|---|---|---|
| Arrival model | Bursty (non-Poisson, shift spikes) | Poisson (analytic assumption) |
| Service time | Lognormal (long tail) | Exponential (memoryless) |
| Mean wait | Measured from simulation | Erlang-C formula |
| **95th-percentile wait** | **Accurate** | **~60% underestimate** |
| What you can see | Per-patient trajectories, queue snapshots | Aggregate statistics only |

## The problem: Hospital Emergency Department

**Resources:** 3 triage nurses, 8 treatment bays, 2 specialist consultants  
**Arrivals:** Mean 3.2 patients/hour, but **bursty** — shift handovers at 8am/4pm/midnight
drive 2.5× spike rates. Real EDs are never Poisson.  
**Service:** Triage ~2 min (exponential); treatment ~40 min mean with 25 min σ (lognormal
— some patients need 2 hours, some are discharged in 15 min); 50% need specialist consult.

**Why M/M/c gets it wrong:**
- M/M/c assumes Poisson arrivals (coefficient of variation = 1)
- ED arrivals have CV > 2 during handover spikes
- Higher CV → longer tail → P95 wait is severely underestimated

## Sample Results (2026-09-07, claude-sonnet-4-6)

### solver=ON — SimPy DES (10,000 patients)

| Metric | SimPy | M/M/c Analytic |
|---|---|---|
| Mean total wait | 62.0 min | 57.0 min |
| Median wait | 50.6 min | — |
| **P95 wait** | **145.6 min** | **97.0 min** |
| Bay utilization | 13.4% | 26.7% |
| Specialist utilization | 19.9% | ~40% |

**The P95 gap is 50%.** M/M/c predicts a 97-minute 95th-percentile wait; the simulation measured 145.6 minutes — because bursty arrivals (2.5× surges at 8am/4pm/midnight handovers) create queue build-ups that Poisson-based formulas systematically miss.

**Wait time distribution:**

| Wait bucket | Patients | % |
|---|---|---|
| 0–10 min | 45 | 0.5% |
| 10–30 min | 2,151 | 21.5% |
| 30–60 min | 3,781 | 37.8% |
| 60–90 min | 2,062 | 20.6% |
| 90–120 min | 1,000 | 10.0% |
| **120+ min** | **961** | **9.6%** |

Nearly 1-in-10 patients waits over 2 hours — a tail the analytic model cannot see.

**Resource utilization is deceptively low:** triage nurses at 1.8%, bays at 13.4%, specialists at 19.9% — yet P95 is 2.4 hours. The burst dynamics that drive the tail are invisible in time-averaged utilization. Specialists (highest utilization at 19.9%) are the binding constraint; simulation identifies them as the highest-leverage target for intervention.

### solver=OFF — LLM M/M/c analysis

A sharp contrast with r123: unlike the unit commitment LLM that hallucinated its own generator data, the r124 LLM correctly used the actual problem parameters (λ=3.2/hr, 3 triage nurses, 8 bays, 2 specialists, 40-min mean treatment) and worked through rigorous step-by-step Erlang-C math. It correctly identified the specialist subsystem (ρ=0.40) as the bottleneck, computed the burst scenario (ρ_bay jumps from 0.267 → 0.667 at 2.5× load), and gave accurate qualitative insight on why M/M/c fails for EDs.

However, the LLM computed per-subsystem wait times in isolation (specialist Wq ≈ 5.7 min at mean load) rather than total end-to-end sojourn — its P95 estimate for the specialist stage alone was 17.1 min, far below the M/M/c total sojourn P95 of 97 min and the simulation's 145.6 min. The LLM correctly described the gap mechanism but could not quantify the combined tail without running the simulation.

**Finding:** solver=OFF LLM is analytically capable but structurally limited — it reasons correctly about each queue stage but cannot integrate burst dynamics into a total-sojourn tail estimate. DES is the only way to measure the 120+ min tail accurately.

## Run

```bash
# solver=ON: SimPy DES (10,000 patients, 1-week simulation)
graf run ~/.graflang/solvers/simpy_des/simpy_des.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF: M/M/c analytic formula + LLM reasoning
graf run ~/.graflang/solvers/simpy_des/simpy_des.graph.yaml \
    --llm claude_cli --param use_solver=false

# With larger cohort (slower but better statistics)
graf run ~/.graflang/solvers/simpy_des/simpy_des.graph.yaml \
    --llm claude_cli --param use_solver=true --param n_patients=50000


```

## Install

```bash
pip install simpy
```

## Background: Discrete-Event Simulation

DES models a system as a sequence of events occurring at discrete time points:
- **Entities:** patients arriving, waiting, being served
- **Resources:** nurses, bays, specialists (capacity-constrained)
- **Events:** arrival, start-service, end-service, departure
- **Clock:** advances to the next scheduled event (not wall-clock time)

SimPy implements DES using Python generators:
```python
def patient_process(env):
    arrive = env.now
    with nurse.request() as req:
        yield req               # wait until nurse available
        yield env.timeout(2)    # triage for 2 minutes
    # ... treatment, specialist ...
    record_wait(env.now - arrive)
```

**What M/M/c captures:** steady-state mean wait under infinite-horizon, stationary Poisson.  
**What DES captures:** transient behavior, burst effects, shift patterns, tail distributions.

## Key ASSERT

```
ASSERT simulation_valid(@sim_json, @mmc_json);
```

Passes when:
1. ≥ 1,000 patients completed (sufficient sample)
2. Simulation P95 wait > 90% of M/M/c P95 estimate (burstiness must raise the tail)

If SimPy is not installed, the recipe runs solver=OFF automatically.

## Why this is a new solver class

All current cookbook-solver recipes (r67–r121) are **optimization problems**:
find x that minimizes/maximizes f(x) subject to constraints.

SimPy DES is a **simulation problem**: given a stochastic process, generate sample paths
and measure statistics. You cannot "optimize" with SimPy alone — but you can:
1. Simulate to understand system behavior (r124)
2. Then optimize staffing levels using those statistics as inputs to an LP/MILP (future recipe)

This is the "simulate-then-optimize" pattern, which matches how real operations research
projects are structured.
