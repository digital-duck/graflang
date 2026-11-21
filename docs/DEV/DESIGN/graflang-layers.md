# Layers: a logical graph that compiles to a flat one (DRAFT, nothing here is implemented)

Date: 2026-11-21
Related: `graflang-semantics.md`

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
- **Interface block (implemented: semantics 3d).** `inputs`, `outputs` (name -> type, optional default and description), `errors` (named routes out), and a one-line
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
3. (Reassessed, see row 13.) `inherits` would be a convenience for a key passed down several levels; it is not needed for isolation. If built: it needs a type and a default owned by the level that declares it.
4. (Answered by the code.) Every node the part's INPUT node triggers starts when the use is triggered (`parts._expand_use`, `starts`); a part's way out is `complete` plus its declared error exits.
5. Does a MUTATE inside a body see the level above? Proposed no: it edits its own level (compare gap #32 for LOOP bodies).

6. **Loop-carried state (corrected after measuring).** An earlier version of this note counted 77 "implicit cross-level reads" in LOOP
   bodies. Classified by what each unbound body `in_X` resolves to, they are: 52 the LOOP's own `in_X` port (already an explicit
   interface: the loop declares the port and an edge feeds it), 19 a loop-state variable (an `outputs: {X: {from: ...}}` entry), 2 the
   iteration counter, and 4 in BATCH (3 its `item_var`, 1 its own `in_`). And `graf validate` already refuses a body `in_X` that is
   none of these (`topology.py` ~181-184, `_check_scope`: boundary ports, loop vars). So the neighbour/scope rule already holds for
   loops, statically checked; the cookbook does not need a rewrite for it.
   What is still loose: (a) loop state is declared as a side effect of `outputs: {from}`, not as state, so a reader of the body cannot
   see which names carry over; (b) `collect` and `fired` outputs are also readable by name inside the body, which nobody intends; (c) the
   runtime fallback (`_inputs_for`, ~line 470) resolves by name in three places at once. Options: keep `outputs.from` and fix (b) only;
   or add `state:` (name -> initial, type) as the explicit declaration, with `outputs: {from}` reduced to reading a state variable out
   of the loop. Decision pending; the owner chose `state:` before these numbers were known.

## 9. Build status

This section tracks the build (the rules live in `graflang-semantics.md`, which stays a spec). Updated 2026-11-21 (last: multi-exit and typed Group). Statuses: done (committed,
tests pass), partial, open. The gap table in `zinets/docs/graph-vision/claude/readme-design.md` is updated once the whole refactoring is
tested and finished, not before.

| # | Item | Status | Where |
|---|---|---|---|
| 1 | Loop-carried values under `state:` (R10a); `collect`/`fired` unreadable in a body; `outputs.from` warns | done | `53d3dc6` |
| 2 | `graf group` / `graf ungroup`: composite as a subfolder, prompts and part references move with it, composites of composites round-trip | done | `0dcf732`, `6687f4c` |
| 3 | Editor: Group and "Open a composite again" (Add node tab); Undo removes the folder | done | `6687f4c` |
| 4 | `graf vis --depth N\|all` (default 0); editor canvas Levels choice | done for `vis` | `7fa94ee`, `26995e0` |
| 4a | `--depth N\|all` on `describe` (not with `--llm`) and `info`; a closed part is named in reads, not its inner nodes | done | this commit |
| 4b | Composites inside composites are a depth each (the loader now records `_part_of` innermost, `_use_parent`, `_use_part`); before, depth 1, 2 and `all` drew the same graph | done | this commit |
| 4c | `graf expand --depth N\|all` is the logical-to-physical step (section 2): `all` is the flat graph the runtime runs; no `compile --lang graf` (it would duplicate `expand`) | done | this commit |
| 4d | `phases.pre.map` and the edge `map:` (semantics R15, 5a): simple pure input transforms; the logical form reads as f on the arrow, the runtime sees it inside the node | done (simple form) | this commit |
| 5 | Neighbour rule enforced (an edge into a composite's inner node is refused); it was not enforced before | done | `906d85f` |
| 6 | Interface block: `workflow.description`, `workflow.errors` as named exits (a control port of the use), `ports: [name]` in compact `use` | done | `906d85f` |
| 7 | Error `code` (optional, unique per part and per composed graph), logged as `part.error` | done | `24b5d0a` |
| 8 | Catalogue `graflang.errors.yaml` (shipped plus one beside the graph), `graf errors` | done | `3c97241` |
| 9 | `spl2graph` (SPL.py) writes `state:` | done | SPL.py `994c5964` |
| 10 | Group with several ways out: the failures are named error exits (`--exit NAME=node.port`, an editor field); the rest must share one normal way out; Ungroup round-trips them | done | this commit |
| 11 | Editor Group: description and exits fields | done | this commit |
| 11a | Editor Group/Ungroup keep the graph file's comments | open | comments are dropped, as for a source edit |
| 12 | A grouped part's inputs and outputs keep the types the graph declares (workflow inputs, typed `ports:`, `port_types`); `TEXT` only where nothing is declared | done | this commit |
| 13 | Scoped context (section 4), reassessed: a part sees only its declared inputs (it cannot read the level above, as `code_parts` notes), a loop body only its `in_*` ports, `state:` and the counter (validate refuses the rest). So isolation already holds. What is left is `inherits`, shorthand for passing one key down several levels | reassessed; `inherits` not built, waiting for a real recipe that needs it | |
| 14a | The 54 recipes in `cookbook_pocketflow/` and `cookbook_solvers/` that warned on `outputs.from` now use `state:` (only that key line changed in each; all validate, no warnings) | done | this commit |
| 14 | Cookbook rewrite as layered folders (section 10) | open | |
| 15 | Recursion (section 7) | open, later | |
| 16 | Update the gap table in zinets `readme-design.md` | after the refactoring is tested and done | |

Open questions still to settle: 3 (type and owner of `inherits` keys), 4 (triggers across the interface with several entry points), 5
(does a MUTATE inside a body see the level above).

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
