# Layers: a logical graph that compiles to a flat one (built; section 9 says what and where)

Date: 2026-11-21, updated 2026-11-22
Related: `graflang-semantics.md`

Status: built, except recursion (section 7). Sections 1 to 6 are implemented and the cookbook is rewritten (section 10); section 9 lists each
item and the commit. The rules that were accepted live in `graflang-semantics.md` (3a named subgraphs, 3d the interface of a composite, R10a state,
R15 input map; tests in `tests/test_semantics.py`). Read the sentences below that say "proposed" or "today" as the design record: where the code and
this text differ, the code and `graflang-semantics.md` win. The gap table in `readme-design.md` is updated once the refactoring is tested and finished.

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

| Q-Id | Status | Question | Description |
|---|---|---|---|
| Q1 | Decided | Is a reference across levels an error, or is a compatibility mode kept? | The neighbour rule is an error, with no compatibility mode. Scan of `cookbook/` (36 graphs, 566 top-level edges, 3 graphs using parts with 8 uses, 11 LOOP bodies): no edge reaches into a part, and no LOOP-body edge names a node outside its body. The real cross-level coupling is implicit: 77 `in_*` ports in LOOP bodies are unbound and read the loop's input or state by name (R7, R10), e.g. `code_pipeline`, `code_parts`, `agent_notes`, `pocketflow/debate`. The redesign drops that behaviour: a body gets a key only through its interface or `inherits`. GraphLang has no user base yet, so there is no migration path and no compatibility flag; the cookbook is rewritten (section 10). (Q6 corrects the count.) |
| Q2 | Decided | Is a composite's body inline or a subfolder, and what is the folder layout? | A subfolder, no inline body. The layout is `<recipe>/<name>/<name>.graph.yaml` plus its own prompts, which is what `graf group` writes and the `_v2` cookbooks use. |
| Q3 | Decided 2026-11-21 | Build `inherits`? | Yes, build it. `inherits` is a convenience, not needed for isolation; the part's input declaration owns the type and default (section 9, row 13a). |
| Q4 | Answered by the code | When does a part's body start, and how does it end? | Every node the part's INPUT node triggers starts when the use is triggered (`parts._expand_use`, `starts`); a part's way out is `complete` plus its declared error exits. |
| Q5 | Decided 2026-11-21 | May a MUTATE edit a level other than its own? | No. A MUTATE edits its own level; a delta naming a node of the level above is refused (pinned by `test_a_mutate_in_a_loop_body_cannot_touch_a_node_of_the_level_above`). |
| Q6 | Decided, built | How is loop-carried state declared, and how do we keep a body from reading names it should not? | Corrected after measuring: an earlier version of this note counted 77 "implicit cross-level reads" in LOOP bodies. Classified by what each unbound body `in_X` resolves to, they are: 52 the LOOP's own `in_X` port (already an explicit interface: the loop declares the port and an edge feeds it), 19 a loop-state variable (an `outputs: {X: {from: ...}}` entry), 2 the iteration counter, and 4 in BATCH (3 its `item_var`, 1 its own `in_`). And `graf validate` already refuses a body `in_X` that is none of these (`topology.py` ~181-184, `_check_scope`: boundary ports, loop vars). So the neighbour/scope rule already holds for loops, statically checked; the cookbook does not need a rewrite for it. What was still loose: (a) loop state was declared as a side effect of `outputs: {from}`, not as state, so a reader of the body could not see which names carry over; (b) `collect` and `fired` outputs were also readable by name inside the body, which nobody intends; (c) the runtime fallback (`_inputs_for`, ~line 470) resolves by name in three places at once. Options were: keep `outputs.from` and fix (b) only, or add `state:` (name -> initial, type) as the explicit declaration, with `outputs: {from}` reduced to reading a state variable out of the loop. Decided: `state:`, built (R10a; section 9, row 1). |

## 9. Build status

This section tracks the build (the rules live in `graflang-semantics.md`, which stays a spec). Updated 2026-11-22 (last: every recipe ported to a `_v2` cookbook). Statuses: done (committed,
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
| 13a | `inherits: [name]` on a `use` (compact; `config.inherits`): passes the level's same-named input without writing the binding; the part's declaration owns the type and default, the level's value must be assignable | done | this commit |
| 13 | Scoped context (section 4), reassessed: a part sees only its declared inputs (it cannot read the level above, as `code_parts` notes), a loop body only its `in_*` ports, `state:` and the counter (validate refuses the rest). So isolation already holds. What is left is `inherits`, shorthand for passing one key down several levels | reassessed; `inherits` built as 13a after the owner's go-ahead | |
| 14a | The 54 recipes in `cookbook_pocketflow/` and `cookbook_solvers/` that warned on `outputs.from` now use `state:` (only that key line changed in each; all validate, no warnings) | done | this commit |
| 14 | Cookbook rewrite as layered folders (section 10): ported recipes live in `cookbook_v2/` (13 staged, `self_refine` in compact form, and 15 copied because they were already compact), `cookbook_solvers_v2/` (all 47) and `cookbook_pocketflow_v2/` (all 42: 8 with composites, 34 flat); tracked in `graflang-recipes.md`. Each is equal to its original on the mock adapter; nothing run with a real model except what the owner tried by hand (`ts_verify`, `stock_report`, `notes_digest`, `code_gen`, `code_pipeline`, `your_book`) | done offline; the originals are to be archived once the owner has tested the `_v2` recipes | `451add1`, `9d87c1f`, `2d4b0e5` |
| 14b | `scripts/port_recipe.py`: compact, name every step after its tool or prompt, infer or take groups (`--ids`, `mv:`, `part/sub`), `graf group`, prettify, validate | done | `451add1`, `9d87c1f` |
| 14c | `graf group` moves a prompt or procedure used by a node inside a loop body with the loop (found porting the loop-heavy solver recipes; before, the part did not validate) | done | `9d87c1f` |
| 14d | YAML written by `graf compact`/`prettier`/the editor never wraps a long line (a fold inside an escape had turned `\n` into `\ n` in a tool's code); `graf compact` reads its output back | done | `978461e` |
| 15 | Recursion (section 7) | open, later | |
| 16 | Update the gap table in zinets `readme-design.md` | after the refactoring is tested and done | |

Section 8's Q3 and Q5 are decided and Q4 is answered by the code (the owner replied "no" to Q4, which I read as no change; to be confirmed).

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

What the rewrite showed (2026-11-22):

- Most recipes are a chain of stages, each with one entry and one normal way out, and `graf group` finds them. A staged recipe reads as 3 to 7 boxes at depth 0. The solver recipes share one shape (prepare, a solver arm, an LLM-only arm).
- A retry loop is already one box (a `LOOP`); what is left around it is bookkeeping (`set_*` steps) that is not worth a composite. 34 PocketFlow recipes are ported flat for that reason, and the recipe says so.
- The loop-heavy solver recipes (`lean_proof`, `neurosymbolic`, `constraint_opt`, `symbolic_math`) keep their loops in long form, so grouping them was done by hand, by reading the trigger edges; it found the `graf group` bug of row 14c.
- A top graph needs the error codes of every part it uses beside it (`recipe_chain` has its own `graflang.errors.yaml`).
- The unbound-port fallback was not removed (section 8, Q6): `graf validate` already refused the unintended reads, so the cookbook needed no change for it; the few lifted loops that read an input from the loop's state keep the checker's warning, and the tests allow no more warnings than the original had.
