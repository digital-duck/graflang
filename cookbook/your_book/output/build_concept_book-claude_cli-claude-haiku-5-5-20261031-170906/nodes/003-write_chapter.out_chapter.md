# Chapter 1: Entropy as Uncertainty and Information

## A Question Before a Formula

Suppose a friend hides a coin under a cup and asks you to guess which side faces up. You have no information, so you can't do better than chance. Now suppose the coin is rigged to land heads 99 times out of 100. Your guesses are now much more reliable, and you are much less uncertain about the outcome.

Entropy is the quantity that measures this difference. It answers a simple question: *how much don't we know about an outcome, given what we can expect from the system?* The idea started in thermodynamics, and the chapters that follow will return to it there. This chapter begins with the version that needs no heat engines and no temperatures, the version Claude Shannon introduced in 1948 to describe communication. Once you can compute uncertainty for a coin, a die, or a string of letters, the thermodynamic version will look like a familiar idea wearing different clothes.

## Two Ways to Describe the Same System

Physicists distinguish two levels of description.

A **microscopic** description specifies everything about each component. For a gas in a box, that means the position and velocity of every molecule. The number of molecules is astronomically large, roughly 10²³ in a cubic centimeter at room conditions, so nobody writes this down.

A **macroscopic** description specifies only a few aggregate properties: pressure, volume, temperature. Many different microscopic arrangements produce the same macroscopic picture. Entropy lives in that gap. It measures how many microscopic possibilities are consistent with what we actually observe.

Keep this two-level picture in mind. Chapter 3 turns it into counting. For now, notice that entropy is not a property of the coin or the gas alone. It is a property of the coin *together with what we know about it*.

## Outcomes, Probabilities, and Surprise

Consider a set of possible outcomes, each with a probability. A fair coin has two outcomes, each with probability ½. A fair die has six outcomes, each with probability ⅙. A certain outcome has probability 1.

When an outcome occurs, how surprised should we be? Intuitively, a rare event is more surprising than a common one. The standard measure of surprise is

$$
\text{surprise}(p) = \log_2 \frac{1}{p} = -\log_2 p
$$

This quantity has three useful properties:

- A certain event (p = 1) has zero surprise, because −log₂ 1 = 0.
- Rarer events (smaller p) have larger surprise.
- For independent events, surprises add. Two fair coin flips together give 2 bits of surprise, and each flip alone gives 1 bit.

The logarithm is what makes the additivity work. A probability of ¼ for two independent events multiplies to 1/16, and log₂ 16 = 4 bits, which is 2 + 2.

## Shannon Entropy

Entropy is the *average* surprise you should expect from a source. If an outcome i occurs with probability pᵢ, its surprise is −log pᵢ, and the average over all outcomes weights each surprise by its probability:

$$
H = -\sum_{i} p_i \log p_i
$$

This is Shannon entropy. The sum runs over all possible outcomes. The minus sign makes H positive, since logarithms of probabilities (which are at most 1) are negative or zero.

The base of the logarithm sets the unit:

- **Base 2** gives **bits**. This is the most common choice in information theory and computing.
- **Base e** (natural logarithm) gives **nats**. Physicists often prefer it. One bit equals ln 2 ≈ 0.693 nats.

Both are the same quantity measured on different scales, just as a distance can be given in meters or feet.

### Worked Examples

**A fair coin.** Two outcomes, each with p = ½:

$$
H = -\left(\tfrac12 \log_2 \tfrac12 + \tfrac12 \log_2 \tfrac12\right) = -\left(\tfrac12 \cdot (-1) + \tfrac12 \cdot (-1)\right) = 1 \text{ bit}
$$

**A biased coin.** Heads with p = 0.9, tails with p = 0.1:

$$
H = -\left(0.9 \log_2 0.9 + 0.1 \log_2 0.1\right) \approx 0.47 \text{ bits}
$$

The rigged coin carries less than half the uncertainty of the fair one. It is predictable most of the time, so its average surprise is low.

**A fair six-sided die.** Six equally likely outcomes:

$$
H = -6 \cdot \tfrac16 \log_2 \tfrac16 = \log_2 6 \approx 2.58 \text{ bits}
$$

**A certain outcome.** Suppose a die with all six faces showing 4. Then p = 1 for one outcome and 0 for the rest:

$$
H = -1 \cdot \log_2 1 = 0 \text{ bits}
$$

Nothing is uncertain, so nothing is learned by observing the outcome.

## Why Uniform Maximizes Entropy

Among all distributions over n outcomes, the uniform one, where every outcome has probability 1/n, has the largest entropy:

$$
H_{\max} = \log_2 n
$$

Intuition supports this. When every outcome is equally likely, no outcome is more expected than another, so you have no basis for a confident guess. Any bias toward some outcomes makes a guess easier, which lowers the average surprise.

The reverse is also true. A certain outcome has zero entropy because there is nothing to be uncertain about. Between these extremes, entropy rises as the distribution becomes more spread out and falls as it becomes more concentrated.

## The Question-Counting Interpretation

Here is the most useful way to read entropy in bits. **The entropy of a source is the minimum average number of yes/no questions needed to identify an outcome.**

Imagine a game where you must identify a card from eight equally likely cards by asking yes/no questions.

1. Is it in the first four? 
2. Is it in the first two of those? 
3. Is it the first of those two?

Three questions always suffice, and no strategy can do with fewer. Three bits of uncertainty required three binary answers. In general, n equally likely outcomes need log₂ n questions. This is exactly the maximum entropy for n outcomes, which connects the two results above.

For unequal probabilities, a clever questioner can exploit the bias. With the rigged coin (p = 0.9 for heads), you can ask "Did it land heads?" first, and you will usually be done in one question. The average number of questions approaches the entropy, 0.47 bits, but never falls below it. This is the sense in which entropy is a *minimum*: it is the best you can do on average, and practical codes such as Huffman coding approach it closely.

## Examples From Language

Language gives a natural source with structure. Consider a random English letter drawn according to its frequency in typical text. Letters such as E, T, and A are common, while Q, X, and Z are rare.

If all 26 letters were equally likely, the entropy would be log₂ 26 ≈ 4.70 bits. Real letter frequencies are uneven, so the single-letter entropy is roughly 4.1 bits. The gap is the redundancy that English carries: the language is more predictable than a random string of letters.

Context reduces uncertainty further. After "th," the next letter is far more predictable than after "q." Shannon used exactly this idea in his 1951 experiments asking people to guess the next letter of English text. Their guesses implied that English carries about one bit per letter once context is taken into account. Redundancy is what makes text compressible and makes it possible to reconstruct a sentence with a missing word.

## Putting It Together

Entropy in this chapter has a single meaning:

- **Uncertainty**: how much we don't know about an outcome.
- **Average surprise**: the expected value of −log p over the outcomes.
- **Information content**: how many bits of answer we need, on average, to pin down the outcome.

These three descriptions are the same quantity. A fair coin is uncertain, surprising on average, and needs one question to resolve. A certain outcome is none of these things. Shannon entropy captures the whole idea in one formula, H = −Σ p log p.

Entropy is not a property of a physical object alone. It depends on the probability distribution we use to describe it. The same gas can have different entropies depending on what we know about its molecules, and this observation will become central when we return to physics. Chapter 2 starts from heat engines and asks what entropy means when the outcomes are energy flows, and Chapter 3 shows how the counting of microstates ties the thermodynamic and information-theoretic versions together.