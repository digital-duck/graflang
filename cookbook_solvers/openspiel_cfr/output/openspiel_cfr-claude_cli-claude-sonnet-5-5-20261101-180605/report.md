=== OpenSpiel CFR — Kuhn Poker (r116) | solver=ON ===

## CFR Report — Kuhn Poker

**Iterations:** 1000  
**Exploitability:** 0.0009 (threshold: 0.05)  
**Converged to Nash:** Yes ✓

### Average Policy at Key Information Sets

| Info set | Pass / Check | Bet / Call |
|---|---|---|
| P1:0 | 0.806 | 0.194 |
| P1:0pb | 1.000 | 0.000 |
| P1:1 | 0.993 | 0.007 |
| P1:1pb | 0.469 | 0.531 |
| P1:2 | 0.416 | 0.584 |
| P1:2pb | 0.001 | 0.999 |
| P2:0b | 1.000 | 0.000 |
| P2:0p | 0.667 | 0.333 |
| P2:1b | 0.664 | 0.336 |
| P2:1p | 0.996 | 0.004 |
| P2:2b | 0.000 | 1.000 |
| P2:2p | 0.001 | 0.999 |

### Known Nash Equilibrium (Kuhn Poker)

> Player 1: Bet with K always (1.0), Bet with J at probability 1/3 (bluff), Pass with Q always. Player 2: Call with K always, Call with Q at probability 1/3, Pass with J always.

### Exploitability Interpretation

| Policy | Exploitability | Meaning |
|---|---|---|
| Perfect Nash | 0.000 | Unexploitable — best response cannot gain |
| CFR avg (this run) | 0.001 | Near-Nash ✓ |
| LLM naive (bet-K-only) | ~0.250 | Exploitable — opponent folds J/Q, always calls K |

── Game Theory Explanation ─────────────────────────────────
1. **Exploitability** is how much an opponent's best response could win against your strategy, beyond the game's value. At 0.0009, a best-responding opponent gains almost nothing. A good player wants it near zero because it means no pattern can be punished.

2. **Equilibrium:** With K, bet or call often; with Q, mostly check, and call a bet about 1/3 of the time; with J, bluff about 1/3 (CFR shows P1:0 ≈ 0.19, which sits within the equilibrium family, since P1's J-bluff rate can range from 0 to 1/3 and is linked to its K-bet rate). Bluffing is optimal because it makes K-bets less readable. If P1 only bet with K, P2 would always fold J and Q, and P1 would win only the small pot. Bluffs with J also put Q in a real dilemma: calling and folding both cost the same in expectation, so P2 is indifferent at 1/3.

3. **Pure strategies fail** because they can be exploited. "Bet only with K" tells P2 that a bet means K, so P2 folds everything else and calls with K only when it gains. P2 then pays nothing for folding. Equilibrium needs each player's mix to leave the opponent indifferent, which only randomization achieves (~0.25 exploitability for bet-K-only).

4. **Generalization:** CFR tracks regret for each decision at each information set and averages strategies over many iterations. This converges to Nash in two-player zero-sum games. Variants (Monte Carlo CFR, abstraction, and neural approximation) scale it to Texas Hold'em, as in Libratus and Pluribus. For sealed auctions or negotiation, the same approach works if the game is modeled with private types and sequential moves. Outside zero-sum or two-player settings, convergence guarantees weaken.