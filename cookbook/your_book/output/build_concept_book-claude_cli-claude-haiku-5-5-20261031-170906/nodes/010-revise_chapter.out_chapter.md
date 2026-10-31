## Chapter 1: Entropy as Uncertainty and Information

Entropy is one of the most widely used and most widely misunderstood words in science. Physicists talk about it as a measure of disorder, engineers as a limit on how efficiently machines can run, and information theorists as the amount of "surprise" in a message. These are not three unrelated ideas. They are three views of one idea: **entropy measures how much we do not know about a system, given what we can observe.** This chapter builds that idea from the ground up, starting with probability and ending with a formula you can calculate by hand.

### Two ways to describe the same system

Consider a box containing a gas. You could describe it in two very different ways.

The **microscopic** description tracks every particle: its position, its velocity, its direction of motion. A cubic centimetre of air at room temperature holds on the order of 10¹⁹ molecules. Recording six numbers per molecule (three for position, three for velocity) at 64 bits per number gives 10¹⁹ × 6 × 64 ≈ 4 × 10²¹ bits, roughly half a zettabyte. That is a large but finite amount of storage. The practical obstacle is that these numbers change constantly: each molecule collides billions of times per second, so a complete microscopic description is out of date almost as soon as it is written.

The **macroscopic** description ignores almost all of that detail. It records only a handful of quantities that can be measured directly: pressure, volume, temperature, the amount of gas. Many different microscopic arrangements produce the same macroscopic readings. Consider a box divided into four equal cells, containing two identical molecules, at most one per cell. There are six distinct arrangements (pairs of occupied cells). Two of them, with both molecules in the left half and with both in the right half, are different at the fine level, since a detector counting molecules in each half would register them differently. Yet a gauge that reads only the number of molecules, the volume, and the temperature cannot tell any of the six apart.

This gap between the detailed description and the coarse one is where entropy lives. When we know only the coarse description, we are uncertain about the fine one, and the number of fine-grained possibilities consistent with what we know is a measure of that uncertainty. Chapter 3 will make this precise for physical systems. For now, let us set the physics aside and study the mathematical core, which works equally well for coins, dice, and text.

### Outcomes, probabilities, and surprise

Suppose an experiment can produce one of several outcomes. A fair coin gives heads or tails. A die gives 1 through 6. A random letter drawn from an English book gives one of 26 letters, plus spaces and punctuation. Each outcome *i* has a probability *p_i*, with every *p_i* between 0 and 1 and all of them summing to 1.

Before the experiment, you are uncertain about the result. After you see it, the uncertainty is gone. How much did you learn? Intuition suggests that a rare outcome is more *surprising* than a common one. If a friend tells you that the sun rose this morning, you learn almost nothing. If they tell you that it snowed in July in your city, you learn a great deal.

We want a measure of surprise, call it *s(p)*, that depends on the probability *p* of an outcome. It should satisfy two requirements:

1. A certain event (p = 1) carries no surprise: *s(1) = 0*.
2. Independent events add their surprises. If you flip two independent coins and learn both results, the total surprise should equal the sum of the surprise from each flip. Since probabilities multiply for independent events (p₁ × p₂), the function must turn products into sums.

Requirement 2 forces the logarithm. Any function satisfying it, and continuous or monotonic in *p* (a mild regularity condition, which rules out pathological solutions), has the form *c* · log(1/*p*) for some positive constant *c*. The constant only fixes the unit, so we take *c* = 1 and write:

$$
s(p) = \log \frac{1}{p} = -\log p
$$

The minus sign makes surprise positive: since probabilities are at most 1, their logarithms are zero or negative. A probability of 1/2 gives surprise −log(1/2), which is 1 bit if we use base-2 logarithms. A probability of 1/1024 gives 10 bits. Rare events carry more information, exactly as intuition demanded.

### Shannon entropy: the average surprise

A single outcome has a surprise. A *source* that produces outcomes has an **average** surprise, weighted by how often each outcome occurs. This average is the Shannon entropy, introduced by Claude Shannon in his 1948 paper founding information theory:

$$
H = -\sum_{i} p_i \log p_i
$$

Read it term by term. For each outcome, multiply its probability by its surprise, then add up the results. Outcomes that are rare contribute little because their probability is small, even though their surprise is large. Outcomes that are common contribute steadily. The result is the expected surprise per outcome, which is the expected information per symbol the source emits.

Two things remain to settle: the base of the logarithm and the units.

- **Base 2** gives entropy in **bits**. One bit is the information in a single fair yes/no choice.
- **Base e** (the natural logarithm) gives entropy in **nats**. Physicists and mathematicians often prefer it, because it fits calculus more naturally.

Converting between them is a matter of arithmetic: 1 nat ≈ 1.443 bits. The formula is the same in either base; only the unit changes. In this book we use bits unless stated otherwise, because bits have a direct operational meaning, which a later section explains.

A convention worth remembering: when *p_i* = 0, the term *p_i* log *p_i* is taken to be 0. This is justified because *p* log *p* approaches 0 as *p* approaches 0, so an outcome that never occurs contributes nothing.

### Worked examples

**A fair coin.** There are two outcomes, each with probability ½.

$$
H = -\left(\tfrac{1}{2}\log_2 \tfrac{1}{2} + \tfrac{1}{2}\log_2 \tfrac{1}{2}\right) = -\left(\tfrac{1}{2}(-1) + \tfrac{1}{2}(-1)\right) = 1 \text{ bit}
$$

A fair coin has one bit of entropy: each flip is a genuine, unresolved choice between two options of equal weight.

**A biased coin.** Suppose heads comes up with probability 0.9 and tails with 0.1.

$$
H = -(0.9 \log_2 0.9 + 0.1 \log_2 0.1) \approx 0.47 \text{ bits}
$$

The biased coin is more predictable, so it carries less uncertainty and less entropy. If you must guess the next flip, you will be right 90% of the time by always guessing heads. That is a statement about prediction, and it is separate from the cost of describing outcomes, discussed in the section on questions below.

**A fair six-sided die.** Each of six faces has probability 1/6.

$$
H = -6 \cdot \tfrac{1}{6}\log_2 \tfrac{1}{6} = \log_2 6 \approx 2.58 \text{ bits}
$$

The die carries more uncertainty than the coin because it has more equally likely outcomes.

**English letters.** Real text is far from uniform. The letter E appears about 12.7% of the time in typical English, while Z appears about 0.07%. Treating letters as independent draws from these single-letter frequencies gives an entropy of about 4.1 bits per letter. A uniform distribution over 26 letters would give log₂ 26 ≈ 4.7 bits. The gap reflects structure in the letter frequencies alone. Context reduces the entropy further. In his 1951 paper "Prediction and Entropy of Printed English", Shannon estimated the entropy of English text by having people guess the next character of printed passages. His experiments gave bounds of roughly 0.6 to 1.3 bits per character, and estimates near 1 to 1.5 bits per character are often quoted. This is far below the 4.1 bits of the independent-letter model, because English is predictable from what has already been written.

### Why uniform maximizes and certainty minimizes

Two facts give entropy its character, and both follow from the formula.

**A certain outcome has zero entropy.** If one outcome has probability 1, every other has probability 0. The sum becomes 1 × log 1 = 0 (since log 1 = 0), and all other terms vanish. There is nothing to be uncertain about.

**A uniform distribution has the largest entropy.** Among all distributions over *n* outcomes, the one that assigns each outcome probability 1/*n* has entropy log₂ *n*, and no other distribution over the same outcomes does better. This is the **principle of maximum entropy**. The intuition is that any departure from uniformity introduces a preference, and a preference is information you have assumed without evidence. Entropy is largest when you have assumed the least.

This principle is more than a curiosity. It is a method. When you know some constraints on a system (say, its average energy) but nothing else, the distribution that maximizes entropy under those constraints is the least biased choice. Chapter 3 shows that this is exactly how the Boltzmann distribution of physics arises.

### Entropy as a count of questions

The most useful interpretation of entropy in bits is operational. Shannon entropy is a **lower bound** on the average number of yes/no questions needed to identify an outcome. No scheme of yes/no questions can beat it on average, and the best achievable average lies less than one question above it.

Consider a fair die, with entropy 2.58 bits. Ask first, "Is it 1 or 2?" If yes, ask "Is it 1?": two questions in total. If no, ask "Is it 3 or 4?", then "Is it 3?" if the answer was yes, or "Is it 5?" if it was no: three questions in total. Averaged over the six faces, the expected number of questions is (2 + 2 + 3 + 3 + 3 + 3)/6 = 16/6 ≈ 2.67. This is the best possible for a single die: Huffman's algorithm produces exactly these code lengths, and no adaptive scheme does better. The entropy, 2.58, is below it, as the bound requires. Shannon's source coding theorem guarantees that the optimum for symbol-by-symbol coding lies between H and H + 1.

The gap between 2.58 and 2.67 can be closed, but only by coding several outcomes together. Take the biased coin, with entropy 0.47 bits. A single flip still needs exactly one question to identify, so the per-flip cost cannot fall below one question when flips are coded one at a time. Now group flips into pairs. The four pairs have probabilities 0.81 (HH), 0.09 (HT), 0.09 (TH), and 0.01 (TT). Assign the codes 0, 10, 110, and 111, giving an average of 0.81 × 1 + 0.09 × 2 + 0.09 × 3 + 0.01 × 3 = 1.29 questions per pair, or 0.645 per flip. Longer blocks push the cost per flip closer to 0.47. The entropy is approached only in the limit of long blocks; it is not reached by asking about single outcomes.

This is why entropy matters beyond theory. A compression algorithm works by assigning short codes to likely symbols and long codes to rare ones. For a long, statistically regular source, whose symbols follow a fixed distribution, the average code length per symbol can approach the entropy of the source but cannot go below it. Real files are only partly regular, and a compressor's model of the data is never perfect, so the entropy is a floor on what the compressor can achieve rather than a target it is guaranteed to reach.

### Key points

- Entropy is a property of a probability distribution: it measures the average uncertainty, or average surprise, of an outcome.
- Surprise is −log *p*. Rare outcomes are more surprising, and independent surprises add. Those two requirements, together with mild regularity, fix the logarithm.
- Shannon entropy H = −Σ p log p is the average surprise of a source, measured in bits (base 2) or nats (base e).
- A certain outcome has entropy 0; a uniform distribution over *n* outcomes has the maximum, log *n*.
- In bits, entropy is a lower bound on the average number of yes/no questions needed to identify an outcome. For a single fair die the optimum is 2.67 questions, against H ≈ 2.58. Coding long blocks of outcomes together brings the cost per outcome arbitrarily close to H.

The next chapter turns from messages to machines. It asks why heat flows from hot to cold, why engines cannot be perfectly efficient, and why a broken cup never reassembles itself. The answers come from the same quantity, applied to heat and temperature rather than symbols and probabilities.