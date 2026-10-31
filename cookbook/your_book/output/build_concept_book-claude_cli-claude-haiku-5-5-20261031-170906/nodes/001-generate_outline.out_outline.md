# Concept Book Outline: Entropy

## Chapter 1: Entropy as Uncertainty and Information

**Key concepts to cover**
- Microscopic vs. macroscopic descriptions of a system
- Probability distributions over outcomes and the notion of "surprise"
- Shannon entropy: H = −Σ p·log p, and its units (bits, nats)
- Entropy as the average information content of a message source
- Maximum entropy for a uniform distribution, zero for a certain outcome
- Intuitive examples: coin flips, dice, English letter frequencies

**Learning objectives**
- Define entropy as a measure of uncertainty over a set of possible outcomes
- Compute Shannon entropy for simple discrete distributions
- Explain why uniform distributions maximize entropy and certain outcomes minimize it
- Interpret entropy in bits as the minimum average number of yes/no questions needed to identify an outcome

## Chapter 2: Thermodynamic Entropy and the Second Law

**Key concepts to cover**
- Heat, work, and the historical origin of entropy in steam-engine efficiency
- Clausius's definition: dS = δQ_rev / T
- The Second Law: entropy of an isolated system does not decrease
- Irreversibility and why natural processes have a preferred direction
- Heat flow between bodies at different temperatures as an entropy-producing process
- Entropy as a state function and the idea of heat death

**Learning objectives**
- State the Second Law of Thermodynamics in terms of entropy change
- Calculate entropy changes for reversible and simple irreversible processes (e.g., heat transfer, isothermal expansion)
- Distinguish reversible from irreversible processes and explain the source of irreversibility
- Describe why the Second Law gives time its arrow

## Chapter 3: Statistical Mechanics and the Link Between the Two Entropies

**Key concepts to cover**
- Microstates and macrostates; counting configurations
- Boltzmann's formula: S = k_B ln W
- Gibbs entropy: S = −k_B Σ p_i ln p_i, and its connection to Shannon entropy
- Why systems evolve toward the most probable macrostate
- Gas expansion and mixing as examples of entropy increase through counting
- Limits of the statistical picture: fluctuations, Maxwell's demon, and the role of information erasure (Landauer's principle)

**Learning objectives**
- Explain Boltzmann's formula and the meaning of the number of microstates W
- Show that Gibbs entropy reduces to Boltzmann's formula for equal probabilities
- Connect Shannon entropy in Chapter 1 to thermodynamic entropy via the constant k_B and the choice of logarithm base
- Discuss how information-theoretic reasoning resolves apparent paradoxes such as Maxwell's demon