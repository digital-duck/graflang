[VAGUE]
The spec "make something useful" has no goal, inputs, outputs, scope, or success criteria. A developer would have to invent the problem and the solution.

Missing or ambiguous:
- **Purpose:** No problem statement or intended user. "Useful" to whom, and for what task?
- **Input/output:** No inputs, outputs, function signatures, or interfaces. Not even a rough shape such as CLI, library, web app, or API.
- **Scope:** No boundaries. Nothing says what is in or out, which platform or language to target, or whether this is a new artifact or a change to an existing one.
- **Success criteria:** No definition of "useful," no acceptance tests, and no way to tell when the work is correct or finished.

Note on context: this repository is GraphLang (a graph-first workflow language with `graf` CLI). If the intended work is a feature or addition to it, a spec that names the target (for example, a new `graf` subcommand, a cookbook graph, or a node type) with one concrete input and output would be enough to proceed.