## Chapter 2: Thermodynamic Entropy and the Second Law

Entropy was not born in an information theorist's notebook. It was born in the sooty world of nineteenth-century engineering, in the struggle to make steam engines work better. Before we can appreciate what entropy means in the language of probability (Chapter 1) or of atoms (Chapter 3), we need to see the problem it was invented to solve: why some processes in nature happen easily and others never happen at all.

### Heat, work, and the steam engine

A steam engine turns heat into motion. Fuel burns, water boils, the resulting steam pushes a piston, and the piston turns a wheel. The engineers who built these machines in the early 1800s asked a practical question: how much of the heat we pour in can we turn into useful work, and how much is inevitably wasted?

Sadi Carnot, a French engineer, answered this question in 1824 with a surprising result. He considered an idealized engine that runs through a *reversible* cycle, one carried out so slowly and gently that the working substance is always in equilibrium with its surroundings. For such a Carnot engine operating between a hot reservoir at absolute temperature $T_H$ and a cold reservoir at $T_C$, the efficiency depends only on those two temperatures, not on the working substance:

$$\eta_{\text{Carnot}} = 1 - \frac{T_C}{T_H}$$

Temperatures here must be absolute (kelvin), so the cold reservoir can never be at absolute zero, and the hot reservoir can never be infinitely hot. Carnot also showed that no engine operating between the same two reservoirs can do better. Every real engine, which is irreversible, has efficiency $\eta \le 1 - T_C/T_H$, with equality reached only in the reversible limit. The bound is a ceiling, not a target that clever design can exceed or a prescription for achieving 100% efficiency; a 100% efficient heat engine is impossible, since $T_C > 0$ and $T_H$ is finite. Some heat must always be dumped into the cold reservoir. This is the first hint that heat is not a fully interchangeable form of energy. Work is high-quality energy; heat is lower-quality energy, and its usefulness depends on the temperature at which it sits.

### Clausius and the birth of a new quantity

Rudolf Clausius, working in the 1850s, took Carnot's insight and gave it a precise mathematical form. He noticed that when you run a reversible engine through a complete cycle, the quantity $\delta Q_{\text{rev}} / T$, summed over the cycle, comes out to exactly zero. Whatever reversible path a system takes, the heat it exchanges, divided by the temperature at which the exchange happens, adds up to nothing when you return to the start.

A sum that vanishes around every closed loop means there is a hidden function of state whose change depends only on the endpoints, not the path. Clausius named this function **entropy**, from the Greek *entropē*, "a turning toward" or "transformation." He defined its infinitesimal change as

$$dS = \frac{\delta Q_{\text{rev}}}{T}$$

The subscript "rev" matters. The equation holds for *reversible* processes, idealized changes carried out so slowly and gently that the system is always in equilibrium. Heat $\delta Q_{\text{rev}}$ flows into the system at temperature $T$, and the entropy $S$ rises by exactly that ratio. Entropy has units of joules per kelvin (J/K).

Two things are worth noticing. First, entropy is a **state function**: $S$ depends only on the current condition of the system (its pressure, volume, temperature, composition), not on how it got there. Second, $dS$ is defined through heat, but $S$ itself is only defined up to an additive constant. Thermodynamics fixes differences in entropy, not an absolute zero. An absolute value, with a natural zero, comes only later, from the Third Law and from the statistical picture of Chapter 3. Until then, the useful quantity is always $\Delta S$. That combination of path-independence and heat-based definition is what makes entropy such a useful bookkeeping tool.

### A worked example: isothermal expansion

Consider one mole of ideal gas held at constant temperature $T$ while it expands reversibly from volume $V_1$ to $V_2$. Because the internal energy of an ideal gas depends only on temperature, the gas absorbs heat equal to the work it does on its surroundings. For a reversible isothermal process, that heat is $\delta Q_{\text{rev}} = p\,dV = nRT\,dV/V$. Integrating,

$$\Delta S = \int \frac{\delta Q_{\text{rev}}}{T} = \int_{V_1}^{V_2} \frac{nR}{V}\,dV = nR \ln\frac{V_2}{V_1}$$

For one mole doubling its volume, with the gas constant $R = 8.314\ \text{J/(mol·K)}$ and $\ln 2 \approx 0.693$, $\Delta S = R \ln 2 \approx 5.76\ \text{J/K}$. The entropy goes up, and it does so because the gas has more room, more places for its molecules to be. We will return to that picture in Chapter 3.

### Free expansion: entropy rises with no heat flow

The isothermal example involves heat, so it leaves open a tempting conclusion: that entropy changes always come from heat exchange. A second example shows otherwise. Suppose the same mole of ideal gas is held in one half of an insulated container, with the other half evacuated. Open the partition, and the gas expands freely into the vacuum until it fills both halves.

No heat is exchanged with the surroundings, because the container is insulated: $q = 0$. No work is done, because the gas pushes against nothing: $w = 0$. The internal energy of an ideal gas is unchanged, since its temperature is unchanged, and so the process is isothermal and isoenergetic. Yet the entropy rises by exactly the same amount as in the reversible isothermal expansion:

$$\Delta S = nR \ln\frac{V_2}{V_1} = R \ln 2 \approx 5.76\ \text{J/K}$$

The reason is that $dS = \delta Q_{\text{rev}}/T$ is defined along a reversible path connecting the same two states. Entropy is a state function, so its change depends only on the endpoints, and any path between them yields the same $\Delta S$. The free expansion is irreversible, so no reversible heat flow actually occurs during it, but the entropy bookkeeping is carried out on a reversible path that the gas could have followed. The rise in entropy here is produced by the irreversibility itself, not by heat crossing the boundary.

### Heat flow: an irreversible process

Now take two bodies, a hot one at $T_H$ and a cold one at $T_C$, and place them in contact. Heat $Q$ flows from hot to cold. The hot body loses entropy $Q/T_H$; the cold body gains $Q/T_C$. The net change is

$$\Delta S_{\text{total}} = \frac{Q}{T_C} - \frac{Q}{T_H} = Q\left(\frac{1}{T_C} - \frac{1}{T_H}\right)$$

The sign depends on the reciprocals of the temperatures, not on the temperatures themselves. Because $T_C < T_H$, both positive, we have $1/T_C > 1/T_H$. Multiplying by $Q > 0$ gives $\Delta S_{\text{total}} > 0$. The cold body gains more entropy than the hot body loses precisely because its smaller temperature makes each unit of heat count for more.

The total entropy of the pair therefore increases. Nothing in the process violates energy conservation; the same $Q$ leaves one body and enters the other. Yet the process is one-way. Heat flows spontaneously from hot to cold, and never, without outside help, from cold to hot. Entropy measures precisely this asymmetry.

Compare this with a reversible version, in which the temperatures differ by an infinitesimal amount and the heat flows slowly enough that the net entropy change is zero. Reversible processes are the idealized limit; real processes always produce entropy. Every spontaneous flow of heat across a finite temperature difference is a small act of waste, a degradation of the energy's ability to do work.

### The Second Law

These observations are summarized in the Second Law of Thermodynamics. In one of its classical forms:

> The entropy of an isolated system never decreases. It stays constant for reversible processes and increases for irreversible ones.

Written as an inequality, for any process,

$$\Delta S_{\text{isolated}} \ge 0$$

The equality holds only for reversible changes, which are never fully realized. The Second Law therefore gives us a direction. Of all the processes that conserve energy, nature selects only those that increase total entropy.

It is worth stating the law carefully, because it is often misquoted. The Second Law concerns **isolated** systems, or the total of a system plus its surroundings. A refrigerator lowers the entropy of its interior, and that is perfectly lawful, because it pumps more entropy out into the kitchen than the food loses. Local decreases in entropy are common; a decrease in the entropy of an isolated whole is not.

### Irreversibility and the preferred direction

Why do natural processes have a preferred direction? Think of a cup of hot coffee cooling on a table. Its heat spreads into the room, and the room warms very slightly. The reverse, a cup spontaneously heating itself by drawing energy out of the air, never happens. Nor does a broken glass reassemble itself, or ink diffuse back into a single drop. Each is an example of an irreversible process, and each carries the entropy arrow.

The source of irreversibility is always some finite departure from equilibrium: a temperature difference, a pressure difference, a concentration gradient, friction, or unrestrained expansion into vacuum. Remove the gradient, and the process approaches a quasi-static limit, one that proceeds through a sequence of equilibrium states and can in principle be reversed. Introduce a finite gradient, and entropy is produced. A quasi-static process is an idealization that real processes approach but never reach; an actual process driven by a finite gap closes that gap by dissipating useful energy into heat spread across more degrees of freedom.

### Entropy and the heat death

In 1865 Clausius summarized the implication of this reasoning in a memorable phrase, in his paper on the mechanical theory of heat: *Die Energie der Welt ist konstant; die Entropie der Welt strebt einem Maximum zu.* The energy of the world is constant; the entropy of the world tends toward a maximum.

The following is a speculative extrapolation, not a result the Second Law establishes on its own. The Second Law applies to the universe only if the universe is truly isolated, which is itself an open question in cosmology. Gravitation complicates the picture. Gravitating systems have negative heat capacity: when such a system loses energy, it can become hotter, because it contracts and its particles speed up. Gravity therefore tends to clump matter rather than spread it evenly, which runs against the simple picture of uniform homogenization.

Even setting gravity aside, the extrapolation is a long one. If the universe is isolated and every natural process increases its entropy, one might argue that temperature differences will eventually even out, and that everything will settle into a uniform, lukewarm equilibrium in which no work can be extracted. This scenario is the so-called **heat death** of the universe. The Second Law alone does not say that stars will burn out or on what timescale; those are claims about the far future that depend on physics beyond thermodynamics. Heat death is best read as a possible consequence the thermodynamic framework suggests, not a settled prediction.

What the Second Law secures is narrower and more solid: in any closed system, the capacity to do useful work is steadily eroded.

### Why time has an arrow

Newton's equations of motion are time-reversible. If you film a planetary orbit and play the film backward, the motion still obeys the laws. The microscopic laws of physics, at the level of individual particles, do not single out a direction of time. Yet the film of a cooling cup played backward looks absurd. Thermodynamics supplies the asymmetry that the underlying laws do not.

This is the sense in which the Second Law gives time its arrow. The direction "forward" is the direction in which entropy increases. Memory, aging, and the growth of records all track this direction, because each is a process that leaves an irreversible trace. We remember the past and not the future partly because the past is the low-entropy state from which the present has been moving away.

This creates a genuine puzzle. The laws governing individual particles are reversible, yet the behaviour of large collections of particles is one-way. Entropy increases in the observed direction even though nothing in the microscopic equations prefers that direction. Resolving this puzzle requires a different way of thinking about entropy, one based on counting the arrangements of particles rather than tracking heat alone. That is the subject of Chapter 3. The answer, in brief, is that systems move toward states that are overwhelmingly more numerous, and the Second Law is, at bottom, a statement about probability.