# Layers: a logical graph that compiles to a flat one (DRAFT, nothing here is implemented)

Status: proposal for discussion. Where it says "today" it describes the code as it is; where it says "proposed" it is open for change. When a
part of this is accepted, its rules move to `graflang-semantics.md` (with tests in `tests/test_semantics.py`) and the gap table in
`readme-design.md` gets a numbered item.

## 1. Problem

A graph is flat. A workflow of thirty nodes is thirty boxes and the wiring between them; the author has to hold the wiring in mind, and
the picture, `describe` and the editor all show every node at once. Parts (`SUBGRAPH`, `resources.parts`) are a first step, but they
are a load-time macro: `load_graph` pastes the part's nodes in with `<use>__<node>` ids and everything after sees one flat graph.
The hierarchy exists only in `_part_of`, for `graf vis`.

Goal: a person writes and reads the *logic* one level at a time, top-down, without dealing with internal wiring. The runtime stays flat.

## 2. Two forms of one program

| | logical graph | physical graph |
|---|---|---|
| for | authors, editor, `describe`, `vis`, reviewers, a mutating LLM | the runtime, `validate`'s race/JOIN checks, `trace` |
| shape | a tree of levels; each level is a small graph | flat nodes and edges (today's long form) |
| rule | a level sees only its own nodes and the *interface* of the composites in it | none beyond today's R1 to R14 |

The compile step logical -> physical is the flattening `parts.py` does today, made a named stage. The runtime gets no new semantics; the
physical graph is what R1 to R14 describe. `graf compile --lang spl|pocketflow` stay as other physical targets.

## 3. Composite node

A composite is a node whose body is a graph with a declared interface. Today's `SUBGRAPH` use is the closest thing; it already checks the
use against the part's inputs and outputs (names, types, defaults) and gives each use its own state. Proposed additions:

- **A composite is a subfolder (decided).** Its body is a part file in a subfolder of the recipe, never an inline block: the parent file
  stays short and readable, and the folder is the unit you open, copy, pin and version. Group (section 6) creates the subfolder and
  moves the selected nodes into it.
- **Interface block.** `inputs`, `outputs` (name -> type, optional default and description), `errors` (named routes out), and a one-line
  `description`. This is all another level may know. Control ports are fixed: `trigger`, `complete`, and an error port when `errors` is set.
- **Neighbour rule.** An edge connects two nodes of the same level, or a node to a port of a composite at that level. An edge may not name
  a node inside a composite. `validate` refuses it with the level's path in the message.

## 4. Scoped context (instead of one global dict)

PocketFlow's shared store lets every node read and write everything. Proposed:

- Each level has a **context**: a dict of the keys its nodes read and write (this is today's port store, grouped by level).
- A composite's body sees its own context plus the keys the interface passes in, read-only. It returns values only through its declared
  `outputs`; it cannot write into the parent's context.
- A key needed several levels down is passed through each interface between. `inherits: [budget]` on a composite is shorthand for
  passing it on; it stays visible at the interface and checkable.
- Within one level, last writer wins as in R5/R6, and the race check (guarantee 2) applies per level.

kwargs-style data (a dict as the default shape of a node's input and output) fits this: a composite's interface is the keys it reads and
writes. Typed `ports:` stay as an optional contract, and become required only at a composite boundary. The effect of dropping declared
ports on `validate` (wiring typos, JOIN deadlock) needs its own note before anything is built.

## 5. Compile: logical to physical

- Each composite is inlined, as parts are today. Ids are the path: `search__rank__score`. Interface ports become plain edges.
- Context keys are prefixed by level the same way, so two levels cannot collide.
- Guarantees 1 to 3 are checked on the physical graph; the neighbour and scope rules on the logical one. A MUTATE delta is applied to a
  logical level and re-compiled; a delta cannot change an interface unless its policy allows it, and the `GUARD`/`MUTATE`/`risky`
  protections apply at every level.
- Errors, logs and `graf trace` show the logical path. The prefixed ids already carry it, so this is a display mapping.
- A composite reports what its body touches and its model-call cost (`partinfo.py` does this for parts); the level above sees the summary.

## 6. Tools

- **`--depth N`** on `describe`, `vis`, `info`, `compact`: depth 0 is the top level with composites as single nodes; each depth is a valid
  graph on its own.
- **Group** (editor): select nodes; allowed only if the cut is clean (edges crossing the boundary become interface ports, and no control
  loop is split). The new composite replaces them. **Ungroup** is the inverse. Both are undoable edits through `GraphEditor`.
- **Compact vs Group.** Compact (`steps:`) is a notation for one level; Group changes the structure. They combine.

## 7. Recursion (later, not in the first step)

A composite whose body contains itself behind a condition is recursion. The physical graph cannot be flattened for an unbounded depth, so
this needs run-time instantiation (a frame per call) and a `max_depth` next to `max_steps`. It is the one case where the runtime would
learn about levels. Do it after sections 3 to 6 are in, and keep `LOOP` (iteration) separate.

## 8. Open questions

1. (Decided: the neighbour rule is an error, no compatibility mode.) Scan of `cookbook/` (36 graphs, 566 top-level edges, 3 graphs using
   parts with 8 uses, 11 LOOP bodies): no edge reaches into a part, and no LOOP-body edge names a node outside its body. The real
   cross-level coupling is implicit: 77 `in_*` ports in LOOP bodies are unbound and read the loop's input or state by name (R7, R10),
   e.g. `code_pipeline`, `code_parts`, `agent_notes`, `pocketflow/debate`. The redesign drops that behaviour: a body gets a key only
   through its interface or `inherits`. GraphLang has no user base yet, so there is no migration path and no compatibility flag; the
   cookbook is rewritten (section 10).
2. (Decided: subfolder, no inline body.) Left to settle: the folder layout (`<recipe>/<name>/<name>.graph.yaml` plus its own prompts).
3. Do `inherits` keys need a type, and who owns the default?
4. Where do `triggers` across the interface end up when a body has several entry points?
5. Does a MUTATE inside a body see the level above? Proposed no: it edits its own level (compare gap #32 for LOOP bodies).

6. **Loop-carried state (found while starting step 1).** The unbound-port fallback is not only accidental leakage: `runtime.py`
   (`_inputs_for`, ~line 470) uses it on purpose for loop state. A `from` output starts as the LOOP's input of the same name, each
   iteration's value is read by an unbound body `in_X`, and R10 depends on it. Dropping the fallback therefore needs an explicit
   replacement, not just a validate error. Proposed: a LOOP declares `state:` (name -> initial value or input, type), the body reads
   only `state` keys and the keys the interface passes in, and each iteration writes new values through declared `outputs`. A body
   `in_X` with no binding and no `state`/interface key is a `validate` error. This turns the 77 implicit reads into either `state:`
   entries (loop-carried) or explicit inputs (constants from the level above, e.g. `spec`, `lang`).
   Needs your decision before the runtime changes; it rewrites R7 and R10 in `graflang-semantics.md`.

## 9. Suggested order

1. Interface block and the neighbour rule in `validate`, on existing parts. (Parts already satisfy it by construction: a use is wired only
   through its INPUT/OUTPUT ports and the expanded ids do not exist before load. Checked by reading `parts.py`, not yet by a test.)
   Then question 6 (loop state), which is the real first change to the runtime.
2. Scoped context and `inherits`.
3. Composite as a subfolder; Group/Ungroup in the editor (create the subfolder, move the nodes).
4. `--depth` on the tools.
5. Recursion, if wanted.

## 10. Cookbook rewrite

The cookbook recipes are use cases, not a specification. After the redesign they are rewritten, not migrated, and the rewrite is the first
test of the layered form:

- A recipe is a folder like a small Python package: a short top-level `NAME.graph.yaml` that reads as the logic, and one subfolder per
  composite (its own graph, prompts and procedures), as modules and files organize a repo.
- The picture follows the structure: `graf vis` draws a level at a time, and `--depth N` opens composites.
- No compatibility with the old flat recipes is kept: the unbound-port fallback (R7/R10) goes, and `graf validate` refuses a cross-level edge or a
  read of a key the interface did not pass.
- Order: rewrite one recipe with a LOOP body that reads its parent implicitly (`code_pipeline`) first; whatever is awkward there decides the
  interface and `inherits` rules before the others are done.
