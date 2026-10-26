# docs/DEV

The design history of GraphLang (the early design discussions, the Qwen-generated drafts and their reviews, and the working design notes with the gap table) is kept private, out of this repository, because it contains the maintainer's chat history.

It lives in the private repository `digital-duck/zinets`, under `docs/graph-vision/`, split by who wrote it:

**`claude/`**, Claude's working notes:

| File | What it is |
|---|---|
| `readme-design.md` | the working design notes: the gap table (numbered, open or resolved) and the written semantics of `LOOP`, conditions, data and the LLM |
| `readme-claude.md` | Claude's review of the original proposal |
| `qwen-file-map.md` | where each Qwen-generated file came from |

**`qwen/IDEATION/`**, the Qwen material:

| File | What it is |
|---|---|
| `readme-qwen.md` | the raw Qwen transcript (very large; search it, do not read it through) |
| `qwen-review-feedback.md`, `work-graph-qwen-review.md` | reviews of the Qwen drafts |

What is public about GraphLang is in the other folders: [`../GUIDE/`](../GUIDE/) (setup, tutorial, user guide, contributor guide) and the top-level [`README.md`](../../README.md).

## Assessment: SPL.py and GraphLang, performance, footprint and a Rust target

*Written 2026-10-24. The measurements are one run on one machine with the mock adapter, so they are indicative only.*

GraphLang is not a second implementation of SPL. SPL.py is the SPL language and its executor. GraphLang is a different language (a graph of nodes) that calls SPL workflows through `procedure_ref`.

### Measured

| | SPL.py (`spl3`) | GraphLang |
|---|---|---|
| Import time | about 0.01 s for the bare import (probably lazy, so it understates the real start-up; a full `spl3 run` was not measured) | 0.27 s (networkx alone is 0.11 s) |
| Memory after import | about 10 MB | about 53 MB |
| One run of `self_refine`, mock LLM | not measured | 0.30 s from the command line, about 7 ms in-process |
| Heaviest dependencies | none that stood out | networkx 19 MB, cedarpy 16 MB |

In a real `claude_cli` run of `cookbook/compliance_audit` the whole run took 18.0 s. Each LLM call took 3.4 to 9.9 s, and the deterministic rule check took 4 to 7 ms (measured when it was an in-process SPL procedure; as a subprocess it is about 20 ms for the `stdlib` engine and 165 ms for `sympy`, on one machine). Graph traversal costs microseconds to milliseconds per node, under 0.1% of the run, so a faster interpreter would not change the wall time.

### Is a Rust target worth it for speed?

No. For LLM workflows there is almost nothing to speed up. A compiled binary would cut the fixed Python start-up (about 0.3 s per CLI call), which only matters if the CLI is launched very often. The compiler is also a stub today: `graf compile` fails because its analyzer calls a networkx function that does not exist, and a Rust target would have to reimplement the expression language, the LLM adapters and the SPL procedure calls.

### The case for Rust is safety, not speed

The maintainer's view (after a visit to UPenn and its Cedar work, and reading Christoph Kern's *Safe Coding: Rigorous Modular Reasoning about Software Safety*, Queue 23(5), 2025, https://research.google/pubs/safe-coding-rigorous-modular-reasoning-about-software-safety/): Rust gives memory safety, and together with Cedar GraphLang can have built-in safety that SPL lacks.

What the paper says (from its abstract, which is all I read): risky operations are wrapped in safe abstractions, modules whose public API is safe by design and which check their own requirements at runtime and in type invariants. Hard reasoning is confined to those modules, and the rest of the code is checked automatically by the type checker. The abstract mentions Rust but not Cedar, so the mapping below is my interpretation, not the paper's claim.

How that maps onto GraphLang:

| Safe Coding idea | GraphLang counterpart |
|---|---|
| Risky operations live behind a safe abstraction | `GUARD` and `MUTATE` are the only places a risky action or a topology change happens, and each asks a Cedar policy first |
| Application code has no risky operations | A graph file contains no code, only nodes and edges, so what it can do is limited to what the node types allow |
| The checker verifies the composition | `graf validate` (and, later, a compiler) can check wiring statically: unreachable nodes, a guarded action reachable without its guard, policies that conflict |
| Local runtime checks in the abstraction | `cedar_guard.py` fails closed (any evaluation error denies), and `MUTATE` checks schema, structure, policy and budget |

What exists today and what does not:

- **Already true in the Python runtime:** Cedar enforcement through `cedarpy` (the official Rust engine), fail-closed. As far as I know SPL.py has no policy layer; its checks are `ASSERT` and oracles.
- **Not true yet:** the static guarantee that every risky action is behind a guard. `graf validate` does not check it, and `SOLVE` with no expression is still a stub that returns true (gap #31).
- **What Rust adds beyond Python:** Python is already memory-safe, so the gain is narrower than it sounds: a single binary with no Python or C-extension dependencies, the Cedar engine linked natively, and a place to run the static checks at compile time. Rust does not make LLM output safe, since prompt injection and a policy that is wrong are not memory errors. Cedar is what bounds what an agent may do.

### Recommendation

1. Keep Python as the runtime for now.
2. Put the safety value first, in Python: make `graf validate` prove that every risky node sits behind a `GUARD`, and close gaps #31 and #32 and give `RECOVER`, `FORK` and `JOIN` real behaviour.
3. Run one recipe through SPL.py and GraphLang and compare cost and failure behaviour. That is the first real evidence for a paper.
4. Treat a Rust target as a later option, justified by a standalone binary and compile-time safety checks, not by speed.
