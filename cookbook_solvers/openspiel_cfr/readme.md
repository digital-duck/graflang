# Recipe 116 — OpenSpiel CFR (Kuhn Poker)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/116_openspiel_cfr` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install open_spiel` (heavy C++ build)
· **Solver class:** S025 (imperfect-information games, CFR)

Solve an **imperfect-information** game — where players hold private information —
with **Counterfactual Regret Minimization (CFR)** via
[OpenSpiel](https://github.com/google-deepmind/open_spiel). This is the step
beyond pure/mixed Nash in normal-form games (r110, r115): here no player can see
the others' private state, so optimal play *requires* a randomized strategy that
balances value-betting and bluffing.

## Background

### Game theory in one paragraph

Game theory studies situations where multiple decision-makers interact and each person's outcome depends on what *everyone* does — not just themselves. A **game** has: players (who decides?), actions (what can they do?), and payoffs (who wins how much?). The central question is: what is the rational strategy when your opponent is also rational and trying to beat you? The answer is the **Nash equilibrium** — a strategy profile where no player can do better by unilaterally switching to something else.

### Perfect vs imperfect information

In chess or Go, both players see the full board — this is a **perfect information** game. Solvers (minimax, AlphaZero) can find optimal play by searching the game tree. In poker, you see your own cards but not your opponent's — this is **imperfect information**. This changes everything: the optimal strategy can no longer be a fixed rule ("always do X") because a smart opponent will observe your pattern and exploit it. The only unexploitable play is a **mixed strategy** — randomizing your actions with specific probabilities, so the opponent can never pin down your hand.

The game-theory ladder in this cookbook:
- r110: 2-player, simultaneous, full information → Nash via nashpy
- r115: N-player, simultaneous, full information → Nash via gambit
- **r116: 2-player, sequential, hidden cards → Nash via CFR** ← the hard case

### What is regret?

**Regret** is a simple intuition: after the game ends, how much do you wish you had played differently? If you folded but would have won by calling, you have regret for the fold. If you bluffed but got called every time, you have regret for the bluff.

More precisely: regret for an action = (what you would have earned by always playing that action) − (what you actually earned). Positive regret means "I should have done that more." Negative regret means "good thing I didn't do that."

### Counterfactual Regret Minimization (CFR)

**CFR** is an iterative algorithm that repeatedly plays the game against itself and adjusts probabilities based on regret. The word "counterfactual" means it asks: *if I had tried to reach this decision point, how much would I have regretted my action there?* — factoring out the opponent's randomness so only your own contribution to reaching that state is counted.

The algorithm in plain steps:

1. Start with a uniform random strategy (every action equally likely at every decision point).
2. Play millions of iterations of self-play.
3. After each iteration, compute regret for every action at every decision point.
4. Shift probability toward high-regret actions (the ones you wish you had played more).
5. The **average policy across all iterations** converges to a Nash equilibrium.

The key theorem (Zinkevich et al., 2007): if both players minimize their average regret, the resulting average strategy pair converges to a Nash equilibrium. Convergence rate: exploitability ∝ 1/√iterations — so 1000 iterations → ~0.001, 1M iterations → ~0.00003.

CFR does not need to know the objective function analytically. It just plays, observes, and adjusts — making it the right tool for imperfect-information games where no closed-form solution exists.

### Exploitability

**Exploitability** measures how much a best-responding opponent can earn against your fixed strategy, per game. Formally it is the sum of each player's individual best-response value against the other player's strategy, divided by 2.

| Exploitability | Meaning |
|---|---|
| 0.000 | Perfect Nash — no opponent can gain anything |
| < 0.05 | Near-Nash — practically unexploitable |
| ~0.25 | Naive strategy — a skilled opponent earns 0.25 chips/hand free |
| > 0.5 | Highly exploitable — major strategic error |

CFR's exploitability decreases monotonically as iterations increase. Actual runs on Kuhn Poker:

| Iterations | Exploitability | Latency | ASSERT (< 0.05) |
|---|---|---|---|
| 100 | 0.0082 | 14.8s | ✓ |
| 1000 | 0.0009 | 17.2s | ✓ |

The 2.4s difference between 100 and 1000 iterations shows that the LLM explanation call dominates latency, not the CFR computation itself. 100 iterations is sufficient for the ASSERT; 1000 iterations reaches effectively the analytic Nash.

### OpenSpiel

[OpenSpiel](https://github.com/google-deepmind/open_spiel) is DeepMind's open-source framework for game-theory research — the standard library for anyone working on multi-agent AI and game-theoretic algorithms. In brief:

- **70+ games** behind one uniform API — `pyspiel.load_game("kuhn_poker")` loads the game; the same code runs on Leduc Poker, Liar's Dice, or Go.
- **CFR and variants** built in: vanilla CFR, CFR+, MCCFR (Monte Carlo sampling for large games).
- **Exploitability tools** that compute the exact best-response gap — critical for verifying convergence.
- **The research backbone** behind superhuman poker agents: Libratus (2017, beat professionals at Heads-Up No-Limit Hold'em) and Pluribus (2019, beat 6-player No-Limit Hold'em professionals) both used CFR as their core algorithm, with abstraction to handle the vast state space.

Here we use tabular CFR on Kuhn Poker — the smallest non-trivial poker variant — so the equilibrium is exact, checkable against the analytic solution, and runs in under 20 seconds.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | OpenSpiel **CFR** (tabular, 1000 iterations) | LLM reasons about poker strategy |
| Guarantee | Converges to Nash; **exploitability < 0.05** (`ASSERT`) | Qualitatively correct (textbook recall) — but **unverified** |
| Verification | `ASSERT cfr_converged` (status OK **and** exploitability below threshold) | — |
| LLM role | Interpret the mixed strategy + why bluffing is optimal | Derives correct 1/3 bluff from reasoning — cannot measure exploitability |

**Exploitability** = how many chips/hand a best-responding opponent could extract
against your fixed strategy. `0.0` = unexploitable (a true Nash equilibrium).

## The game — Kuhn Poker

The smallest non-trivial poker variant:

- 2 players, 3 cards (**J < Q < K**), each antes 1 chip and gets one private card.
- Player 1 acts first (**Pass** or **Bet** 1 chip); Player 2 responds; showdown if needed — higher card wins the pot.
- The tension: betting signals strength **and** enables bluffing. Since neither
  player sees the other's card, the only unexploitable play is a **mixed**
  (randomized) strategy.

**Known analytic Nash:** P1 bets K always, **bluffs J at probability 1/3**,
passes Q; P2 calls K always, **calls Q at 1/3**, folds J.

## Run results — solver=ON vs solver=OFF

All runs: `claude_cli` / `claude-sonnet-4-6`, Kuhn Poker.

| Metric | solver=ON (100 iter) | solver=ON (1000 iter) | solver=OFF |
|---|---|---|---|
| Timestamp | 2026-09-07 08:17:32 | 2026-09-07 08:04:45 | 2026-09-07 08:04:57 |
| Tokens in | 492 | 492 | 251 |
| Tokens out | 345 | 464 | 739 |
| Total tokens | 837 | 956 | 990 (+18%) |
| Latency | 14.8s | 17.2s | 48.7s (2.8×) |
| Exploitability | **0.0082** (verified) | **0.0009** (verified) | ~0.25 (not computed) |
| ASSERT passed | ✓ | ✓ | — |
| LLM calls | 2 | 2 | 1 |

### The surprise: solver=OFF gets the strategy right

Unlike r112 (where the LLM's recommendation was wrong on all three parameters), the solver=OFF LLM **correctly derives the equilibrium strategy** — "bluff J roughly 1 in 3 times, call Q roughly 1 in 3 times" — and explains precisely why pure strategies fail. It even articulates the indifference argument that underpins the Nash equilibrium.

This is not generalizable reasoning; it is **textbook recall**. Kuhn Poker is a canonical game-theory example that appears in virtually every introductory text on extensive-form games. The LLM has seen this solved problem in its training data. Contrast with r112 where the objective function was a proprietary black-box simulation the LLM could not have encountered anywhere.

### What the LLM cannot do

Even when strategy recall is correct, two gaps remain:

| Capability | solver=OFF | solver=ON |
|---|---|---|
| State the optimal mixed strategy | ✓ (textbook recall) | ✓ (computed) |
| Measure exploitability numerically | ✗ — cannot compute | ✓ — 0.0009 |
| Verify the strategy is actually Nash | ✗ — asserts, cannot prove | ✓ — ASSERT gate |
| Scale to novel/larger games | ✗ — recall collapses | ✓ — CFR scales |

The "~0.25 exploitability" label in the solver=OFF output is a pre-written assumption in the recipe's output format, not a computed value. Solver=OFF cannot measure exploitability at all.

### Why CFR matters beyond Kuhn Poker

The LLM's success here is an artefact of game familiarity. For Leduc Poker (6 cards, 2 streets), Texas Hold'em (partial recalls), or any novel imperfect-information game — sealed auctions, multi-round negotiation with private signals, sequential mechanism design — the LLM has no textbook to recall from and CFR is the only systematic path to a verifiable Nash. The recipe demonstrates the principle on a tractable game precisely so that the algorithm generalises when the game no longer fits in a textbook.

### Key takeaway

solver=ON is 2.8× faster and produces a verified exploitability of 0.0009. Solver=OFF is correct here — but only because this game is famous. The value of CFR is not that it beats the LLM on Kuhn Poker; it is that it gives the same convergence guarantee on every finite extensive-form game, including the ones the LLM has never seen.

## Example output (solver=ON, 1000 CFR iterations)

```
## CFR Report — Kuhn Poker
**Iterations:** 1000   **Exploitability:** 0.0009 (threshold: 0.05)   **Converged to Nash:** Yes ✓

### Average Policy at Key Information Sets (Pass/Check | Bet/Call)
| P1:0 (J) | 0.806 | 0.194 |   ← bluffs J ~19% ≈ 1/5 (analytic: 1/3)
| P1:2 (K) | 0.416 | 0.584 |   ← bets K most of the time
| P2:0p (J, facing pass) | 0.667 | 0.333 |
| P2:2b (K, facing bet)  | 0.000 | 1.000 |   ← always calls with K

### Exploitability Interpretation
| Perfect Nash       | 0.000 | Unexploitable |
| CFR avg (this run) | 0.001 | Near-Nash ✓ |
| LLM naive (bet-K only) | ~0.250 | Exploitable — P2 always folds to bets |
```

CFR reaches exploitability 0.0009 — effectively the analytic equilibrium — and `ASSERT cfr_converged` passes. The LLM then explains *why* the 1/3 bluff is optimal: it keeps P2 **indifferent** between calling and folding, so no pure counter-strategy can gain edge.

## Run

```bash
# solver=ON — OpenSpiel CFR (1000 iterations by default)
graf run ~/.graflang/solvers/openspiel_cfr/openspiel_cfr.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF — LLM strategic reasoning baseline
graf run ~/.graflang/solvers/openspiel_cfr/openspiel_cfr.graph.yaml \
    --llm claude_cli --param use_solver=false

# vary iterations
graf run ~/.graflang/solvers/openspiel_cfr/openspiel_cfr.graph.yaml \
    --llm claude_cli --param use_solver=true --param n_iterations=100

```

## Install

```bash
pip install open_spiel      # heavy C++ build; Linux wheels usually resolve
```

Or via the bundled extra: `pip install "spl-llm[solver]"`. If the wheel fails to
build, see the OpenSpiel install docs (source build / conda).

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_game_description()` | Return the Kuhn Poker description + known Nash as JSON |
| `solve_with_cfr(n_iterations)` | Run CFR; return exploitability + average policy |
| `cfr_converged(result_json)` | ASSERT gate: status OK **and** exploitability < threshold |
| `format_cfr_report(result_json)` | Render policy table + exploitability comparison |
| `format_report_solver_on / _off` | Assemble the final report |

## Why game-play is important — not just for kids

Games are not entertainment with a side-effect of learning. They *are* learning, delivered through the most efficient mechanism humans have: immediate feedback on consequential decisions.

When you play poker seriously, you are running CFR in your own head without knowing it. Every hand where you bluffed too much and got called is a regret signal. Every hand where you folded and would have won is a counterfactual. Over thousands of hands the average of those adjustments converges — experienced players develop intuitions that match the analytic Nash without ever seeing a formula.

**Ancient Chinese wisdom arrived at the same insight 2,500 years ago.** Sun Tzu's [*The Art of War*](https://www.gutenberg.org/ebooks/132) is a game-theory text written before game theory had a name. Its central premise: *all conflict is played under uncertainty* — you never have complete information about the enemy's position, intent, or capability. The strategic principles that follow are exactly what CFR formalises:

- "All warfare is based on deception" → mixed strategies; a predictable strategy is exploitable
- "Know your enemy and know yourself" → model the opponent's information set, not just your own
- "Supreme excellence consists in breaking the enemy's resistance without fighting" → find the dominant strategy that makes resistance futile (the SPNE in r111: the follower always undercuts, so the leader pre-empts by pricing Low)
- "Appear weak when you are strong, strong when you are weak" → value-bet and bluff at calibrated frequencies so the opponent cannot distinguish them

CFR discovered these principles computationally in poker; Sun Tzu observed them empirically in warfare. The underlying structure is the same: sequential decisions with hidden information, where the optimal strategy must be mixed to prevent exploitation.

**This is not just for kids.** Games have always been how serious strategists train:

- **Military**: war games have been used by professional militaries since the Prussian *Kriegsspiel* (1812). The US military's NTC (National Training Center) and RAND Corporation's simulations are games in the game-theory sense — sequential decisions with hidden information about the adversary.
- **Business**: negotiation training, competitive strategy, and auction design all draw explicitly on game theory. When telecom companies bid billions for spectrum licences, they hire game theorists who solved the same kind of problems CFR solves.
- **Finance**: market-making, options pricing (Black-Scholes assumes players can hedge optimally), and high-frequency trading are all games with hidden information about other participants' intent.
- **Diplomacy and international relations**: the Cold War's mutual assured destruction (MAD) doctrine is the Nash equilibrium of a two-player game where defecting (first strike) is dominated — the same logic as the Prisoner's Dilemma in r110.

**What games teach that lectures do not:**

| Learning mode | What is transferred | Retention |
|---|---|---|
| Lecture / textbook | Declarative knowledge ("Nash equilibrium is...") | Low — memorized, not applied |
| Problem sets | Procedural skill on pre-defined cases | Medium — applies in exam conditions |
| Game play | Strategic intuition built from regret | High — embodied, generalises to novel situations |

The difference between knowing the definition of Nash equilibrium and *feeling* why a pure strategy is exploitable is the difference between reading about cycling and being able to ride a bike. CFR teaches it computationally; a card game teaches it experientially. Both are more durable than a definition.

**The Libratus and Pluribus findings reinforced this.** When CMU's Libratus beat the top heads-up No-Limit Hold'em professionals in 2017, it did not memorize human-played hands — it played trillions of hands against itself via CFR. The strategies it discovered included bluffing and bet-sizing patterns that professionals had not identified in decades of play. The game had been played by humans for over a century; a CFR agent found unexploited edges in weeks.

- [Superhuman AI for heads-up no-limit poker: Libratus beats top professionals](https://doi.org/10.1126/science.aao1733) — Brown & Sandholm, *Science* 2017
- [Superhuman AI for multiplayer poker: Pluribus](https://doi.org/10.1126/science.aay2400) — Brown & Sandholm, *Science* 2019
- [OpenSpiel: A Framework for Reinforcement Learning in Games](https://arxiv.org/abs/1908.09453) — Lanctot et al., 2019

**The duality runs deeper than game theory — it is rooted in physics.** Classical mechanics is deterministic: given initial conditions, Newton's laws predict the future exactly. Quantum mechanics is irreducibly probabilistic: Heisenberg's uncertainty principle means no measurement can simultaneously pin down position and momentum — the best you can do is a probability distribution. These are not two approximations of one truth; they are two fundamentally different regimes of reality, each with its own appropriate mathematics.

This duality has now found a second home in computer science — and maps onto hardware with striking precision:

| Domain | Deterministic pole | Probabilistic pole |
|---|---|---|
| Physics | Classical mechanics (Newton, Laplace) | Quantum mechanics (Heisenberg, Bohr) |
| Mathematics | Exact proof, formal logic | Probability, statistics, stochastic processes |
| Computation | Algorithms: LP simplex, B&B, CFR | Learning: gradient descent, neural networks |
| Hardware | **CPU** — sequential, exact, branch-predictor | **GPU** — massively parallel, approximate, SIMD |
| SPL runtime | `--solver` flag → deterministic solver | `--llm` flag → probabilistic LLM |
| Game theory | Pure strategy (deterministic) | Mixed strategy (probabilistic) |

The CPU is engineered for deterministic, sequential, exact computation — deep branch prediction, out-of-order execution, large cache hierarchies to serve one thread as fast as possible. The GPU is engineered for massively parallel approximate computation — thousands of simple cores doing matrix multiply in lockstep, optimised for the statistics of gradient descent. Neither is an approximation of the other; they are genuinely different computational regimes in the same box.

SPL's `--solver` / `--llm` two-flag architecture is not a software convenience — it is a recognition that these two poles of computation require different hardware, different algorithms, and different correctness guarantees. The solver runs on CPU (or FPGA); the LLM runs on GPU. Routing each task to the appropriate regime is what makes the system both correct and efficient. Blurring the boundary — training the GPU to do what the CPU already does exactly — wastes both poles.

Sun Tzu knew this intuitively: *know your terrain*. The terrain of imperfect-information strategy is probabilistic; the terrain of resource allocation and constraint satisfaction is deterministic. Using the wrong tool on the wrong terrain is how battles and optimizations are lost.

**The practical implication for education:** if you want to teach strategic reasoning — not just game theory vocabulary — the substrate should be a game, not a lecture. The regret-and-adjust loop *is* how learning works. Kids who play card games, board games, or video games competitively are building the same machinery that CFR formalises. The algorithm is a description of what experienced players already do intuitively. Making that explicit is what game theory adds; making it *fast and scalable* is what OpenSpiel adds.

## Related recipes

- **r110** — Nash equilibria, 2-player normal-form (nashpy)
- **r115** — N-player normal-form Nash (pygambit)
- **r116** — *this recipe:* imperfect-information, sequential games (OpenSpiel CFR)

The progression r110 → r115 → r116 tracks the game-theory difficulty ladder:
2-player → N-player → **hidden information**, where mixed strategies and CFR become
essential.
