# Graph Dialects: zinet ⇄ ConceptBook ⇄ graph-code ⇄ Graph-Lang

Decision D7 in `graflang-design.md` (Wen: "now"): write the mapping between the graph dialects before any of them grows further.

**Principle (the "two layers" rule)**
- **Static layer** — graphs that *describe* something and never run: knowledge/curriculum (ConceptBook), app blueprints (graph-code), dependency graphs (zinet), project memory (work-graph).
- **Executable layer** — Graph-Lang workflows (`*.graph.yaml` with `workflow:`), which *run* and may read and write static graphs.
- **No fifth file format.** Interoperate through one shared in-memory model plus per-dialect readers/writers, not by merging files into one schema.

**Sources and confidence**
- Read: `zinet/README.md`, `zinet/schemas/graph.schema.json`, `zinet/docs/DEV/readme-ecosystem.md`, `graph-code/CLAUDE.md` (schema notes), `graph-code/docs/DEV/BUILD/blueprint-schema-v2.2.md` (first 80 lines), `apps/todo/blueprint/backend.graph.yaml` (head and `function:` block), `cb-linalg/public/domains/graph.yaml` (head), graflang `graflang-ir.json`, and the `self_refine` and `concept_book` cookbook graphs.
- **Not verified**: the implementation of `zinet.formats.detect`, graph-code's loader (`loader.py`), work-graph's layer files beyond `domain.py`'s docstring, and `apps/etl_workflow.graph.yaml`. Rows marked *(inferred)* come from docs only.

---

## 1. Inventory

| | zinet | ConceptBook (flat v1.0) | graph-code (Unified Duality v2.1/2.2) | Graph-Lang |
|---|---|---|---|---|
| Purpose | store and check a dependency graph | curriculum: concepts → mastery | blueprint an app/curriculum, then build | execute a workflow |
| Detect by | `primitives`/`concepts`/`applications` as **lists** | same three keys as **mappings** | `form:` (+ `function:`, `blueprint:`, `domain_type`) *(inferred)* | `workflow:` + `nodes:` + `edges:` |
| Node shape | list item `{id, label, deps, edge_types, meta}` | key in a layer mapping `{defines, tier, composed_of/needs, ...}` | key in `form.primitives` / `form.nodes` `{kind, defines, composed_of, tier, spec, verification, docs}` | list item `{id, type, ports, config}` |
| Edge shape | implicit: `deps` on the dependent node | implicit: `composed_of` (concepts), `needs` (applications) | implicit: `composed_of`, `depends_on`, `enriched_by`, `optionally_depends_on`, `needs`; plus `function.calls/exports`, `function.transitions` | explicit list `{source: node.port, target: node.port, type: triggers\|binds}` |
| Edge types | `depends_on`, `data_flow`, `prerequisite`, `constraint`, `inheritance` | none (implied by field name) | mandatory (`composed_of`, `depends_on`) vs optional (`enriched_by`, `optionally_depends_on`); app-level `needs` | `triggers` (control), `binds` (data) |
| Cycles | no (DAG) | no | `form_graph` no; `event_graph` and `flow_graph` yes | yes (loops, retries) |
| Executes | no | no | no (drives a build) | yes |
| Imports | `imports: [files]` | no | aliased imports in `integrated` graphs | `resources` (procedures, prompts, policies), subgraphs |
| Version key | `version: "1.0"` | `domain:` etc. | `schema_version` 2.1 / 2.2 in `blueprint:` | `version: "1.0-graph"` |
| Tool | `zinet` | `cba`, `cb_pipeline` | `grafcode` / `gfc` | `graf` |

---

## 2. Concept Crosswalk

| Concept | zinet | ConceptBook flat | graph-code v2.x | Graph-Lang |
|---|---|---|---|---|
| **Identity** | `id` | mapping key | mapping key | `id` |
| **Layer / kind** | layer list (`primitives`, `concepts`, `applications`) | layer mapping | `form.primitives` vs `form.nodes` (+ `kind:` `concept/doc/...`), `applications` | `type` (GENERATE, SOLVE, ...) |
| **Dependency** | `deps` (+ `edge_types`) | `composed_of`, `needs` | `composed_of`, `depends_on` (mandatory); `enriched_by`, `optionally_depends_on` (optional); `needs` (app-level) | `binds` (data), `triggers` (control) |
| **Domain payload** | `meta` (opaque) | sibling fields (`defines`, `tier`, `verifier`) | `defines`, `tier`, `spec{interface,contract}`, `verification`, `docs` | `config` |
| **Abstraction level** | derived from layers | `tier` | `tier` | subgraph nesting |
| **Verification** | none | `verifier` field | `verification:` list (backend: pytest, tests) | `ASSERT` / `GUARD` nodes |
| **Routing** | none | none | `function.transitions {from,to,action,condition}` + `entry` (workflow profile) | `triggers` from a named control port; `_route` from `EVALUATE`/`ASSERT`/`GUARD` |
| **Step lifecycle** | none | none | `node.phases {pre, execute, post}` (workflow profile; "only `execute` is meaningful" today) | proposed: `config.phases` (see §5) |
| **Cycles allowed** | no | no | `flow_graph` / `event_graph` yes | yes |
| **Interface / contracts** | none | none | `function.exports`, `function.calls`, call contracts | workflow `inputs`/`outputs`; port types (proposed E2) |
| **Provenance** | none | none | `blueprint:` (id, provenance, lineage, drift) | run logs (JSONL), per-node outputs |
| **Imports / composition** | `imports` | none | aliased imports, `integrated` graph of graphs | subgraphs, `procedure_ref` |
| **Settings** | none | none | `${{ settings.KEY }}` | bindings (proposed E6) |

Key observation: **graph-code's workflow profile and Graph-Lang overlap heavily** (action-routed transitions, a pre/execute/post phase split, cycles allowed, `entry`). Both were inspired by PocketFlow. That overlap is the main consolidation risk and the main opportunity.

---

## 3. Shared Core Model

Define one in-memory model that every dialect reads into and writes out of. It is the "LLVM IR" role that zinet already claims; this document narrows what it must hold.

```
Graph    {id, kind: static|executable, nodes: [Node], edges: [Edge], meta: {}}
Node     {id, layer|type, label?, ports?: {name: {dir, type}}, payload: {}}      # payload = zinet `meta` / graph-code spec... / graflang `config`
Edge     {src: id[.port], dst: id[.port], type: EdgeType, label?: str, optional?: bool, payload: {}}
EdgeType = depends_on | prerequisite | composed_of | constraint | inheritance
         | data_flow  | control_flow                         # data_flow == `binds`, control_flow == `triggers`
```

Rules:
1. **Static and executable graphs share the model**, differing in `kind` and the allowed node/edge types, so `zinet validate/diff/slice/render` can work on any of them.
2. **Round trip fidelity per dialect:** each reader keeps unknown fields in `payload` and the writer restores them, so reading then writing a file does not lose data (zinet already has comment-preserving YAML in `zinet.roundtrip`).
3. **Optionality is an edge flag** (`optional: true`), replacing graph-code's `enriched_by`/`optionally_depends_on` field names in the shared model.
4. **Port information is optional** and only meaningful for executable graphs.

Additive changes to zinet's `EdgeType` (currently `depends_on`, `data_flow`, `prerequisite`, `constraint`, `inheritance`): add `composed_of`, `control_flow`, and an `optional` flag. Additive only; existing files remain valid.

### 3.1 Where it lives: `zinet.model` (decision: Wen, "move into zinet now")

The shared model lives in **zinet**, so graph-code, work-graph and graflang all import it from one place and no one has to rework imports later. Facts about zinet today that shape how:

- zinet is light: dependencies are `networkx`, `pydantic`, `pyyaml` only. The model fits those; **no new dependencies**.
- `zinet.schema.Graph` is the *zinet-dialect file format* (three fixed layers via the `Layer` enum, `deps` + `edge_types`, `extra="forbid"`). It stays as is. The shared model is a **new module** (`zinet.model`) that is *not* the file format; it is the in-memory interchange form. Add adapters `Graph ⇄ GraphModel` so every existing zinet command and file keeps working unchanged.
- zinet's algorithms (`zinet.algorithms`, `zinet.dag`) work on a `networkx.DiGraph` pointing **dependency → dependent**. The model must keep this convention: edge `src → dst` means *src is a prerequisite/producer of dst*. This already matches graflang (`binds`: producer port → consumer port; `triggers`: predecessor → successor) and graph-code (`form_graph`: `dep → node`). So `GraphModel.to_networkx()` yields something the existing algorithms accept for the acyclic part.
- Executable graphs may have cycles (loops, retries). `to_networkx()` returns a `MultiDiGraph` for them, and acyclicity-based algorithms apply to the static/`mandatory` subgraph only (`ensure_acyclic` stays opt-in).
- `zinet.formats.detect` is extended (§4.2). `explain_foreign` stops saying ConceptBook graphs "cannot be read" once the M2 reader lands.
- Release: new minor (`0.3.0`), additive; graflang and graph-code pin `zinet>=0.3`. graflang already depends on zinet (`formats`, `vis`), so no new dependency edge appears.

Layout sketch (names are proposals, to be confirmed in M1):

```
zinet/
  schema.py         # unchanged: the zinet-dialect file format (Graph, Node, Layer, EdgeType+)
  model.py          # NEW: GraphModel / NodeModel / EdgeModel (pydantic), kind=static|executable, version
  adapters/         # NEW: readers/writers per dialect -> GraphModel
    zinet.py        #   Graph  <-> GraphModel
    conceptbook.py  #   flat mapping dialect (ConceptBook, graph-code v1.0) -> GraphModel (+ writer keeping original shape)
    graphcode.py    #   graph-code v2.x form space -> GraphModel (projection; keeps the rest in payload)
    graflang.py     #   workflow nodes/edges <-> GraphModel (ports preserved)
  formats.py        # detect() extended
```

What the model must **not** do: execute anything, import `cedarpy`/`dd-llm`/SPL, or know about Cedar policies and LLM adapters. Those stay in graflang.

### Edge type registry (normalization table)

| Dialect field | → Shared `EdgeType` | Notes |
|---|---|---|
| zinet `deps` without `edge_types` | `depends_on` | |
| zinet `edge_types: prerequisite` | `prerequisite` | |
| ConceptBook `composed_of` | `composed_of` | concept built from primitives/concepts |
| ConceptBook `needs` | `depends_on` | application-level |
| graph-code `composed_of` | `composed_of` | |
| graph-code `depends_on` | `depends_on` | |
| graph-code `enriched_by`, `optionally_depends_on` | `depends_on` / `composed_of` with `optional: true` | |
| graph-code `needs` | `depends_on` (application-level) | |
| graph-code `function.transitions` | `control_flow` with `label: action` | may cycle; goes to the flow graph |
| Graph-Lang `triggers` | `control_flow` (src/dst are `node.port`) | |
| Graph-Lang `binds` | `data_flow` | |

---

## 4. Conversions

### 4.1 Matrix

| From → To | Loss | Plan |
|---|---|---|
| **ConceptBook flat → zinet** | none for structure; fields go to `meta` | One-way **normalizing reader** in zinet (the open question in zinet's notes: answer **yes, read it**). Writer keeps the original dialect when the file came from ConceptBook. Acceptance: load `cb-linalg/public/domains/graph.yaml`, run `zinet validate --strict`. |
| **zinet → ConceptBook flat** | `edge_types` other than composition/needs, `label`, `imports` | Best-effort exporter, mainly for tooling; not a priority. |
| **graph-code `form` → zinet** | `function`, `events`, `verification`, `blueprint`, `spec` text (kept in `meta` or a sidecar) | **Projection** of the form space only: `form.primitives` → primitives; `form.nodes` → concepts (or applications when capstone) ; edges per the registry. Enables `zinet slice/diff/render` on app blueprints. graph-code already imports zinet's algorithms (`zinet.algorithms`), so this is mostly a reader. |
| **zinet → graph-code** | n/a | Not supported; graph-code blueprints need `spec`/`verification` that zinet does not carry. |
| **ConceptBook flat ↔ graph-code flat v1.0** | none | graph-code already loads flat v1.0 by converting to v2.1; reuse that converter as the reference implementation. |
| **graph-code `workflow` profile → Graph-Lang** | `phases.pre/post` bodies become declarative `phases` (E1) if expressible; free-form text hooks are flagged | `form.nodes` → nodes (type inferred from `kind`/`phases.execute`); `function.transitions {from,to,action}` → `triggers` from a control port named `action` (create the port); `entry` → `INPUT.entry`. Data dependencies: graph-code `depends_on` has no port names, so **`binds` must be synthesized** (needs port naming) or authored. |
| **Graph-Lang → graph-code `workflow`** | `binds` (port-level data) collapses to `depends_on`; port types lost | Exporter for documentation and for graph-code's drift/visualization tools. |
| **Graph-Lang → zinet (static skeleton)** | ports, config | Node ids + edges per the registry: `triggers` → `control_flow`/`depends_on`, `binds` → `data_flow`. Already effectively done by `zinet.vis` for drawing; extend to `diff`/`slice` (e.g. "what does this node depend on"). |
| **zinet → Graph-Lang** | n/a | Not a conversion. A workflow *consumes* a zinet graph as data (§6). |
| **SPL ⇄ Graph-Lang** | see `graflang-design.md` E7 | separate track (G1) |

### 4.2 Detection rules (extend `zinet.formats.detect`)

Content-based, first match wins. File names stay a convention only.

| Test | Result |
|---|---|
| top-level `workflow` with `nodes` and `edges` lists | Graph-Lang |
| top-level `form` mapping or `blueprint` / `domain_type` | graph-code (v2.x) |
| top-level `primitives` / `concepts` / `applications` all **lists** | zinet |
| same keys as **mappings** with `composed_of` / `needs` | ConceptBook / graph-code flat v1.0 |
| otherwise | unknown; report what was expected |

Note: the plain-`graph.yaml` name may legitimately hold any static dialect, and the tools already tell the user which command to use instead of failing with a schema error. Adding graph-code detection to zinet closes the gap (zinet's "recognising each other's files" is listed as to-do there).

---

## 5. Aligning the Workflow Lifecycle (follow-up to D1)

Graph-code's workflow profile already defines `node.phases: {pre, execute, post}` (ETL-style: `pre` for state prep/validation, `execute` the body, `post` for formatting/routing), and `function.transitions {from,to,action,condition}`. The Graph-Lang design (E1) proposed `prepare` / `execute` / `finalize`; the owner settled on the short names `pre` / `exec` / `post`.

**Decision:** use `phases: {pre, exec, post}` inside Graph-Lang `config`. `pre` and `post` match graph-code's names; graph-code's `execute` becomes `exec` (a one-word rename in the converter), so the two workflow forms stay convertible. Keep Wen's decision (declarative-only): `pre` and `post` hold schema checks, mappings and routing predicates, not code. Retry/fallback/timeout live under `exec` (only `exec` is retried).

```yaml
config:
  phases:
    pre:     {require: [in_topic], defaults: {in_style: concise}}
    exec:    {timeout_s: 60, retry: {max: 3, wait_s: 2, on: [transient, invalid_output]}, fallback: {route: error}}
    post:    {out_schema: {...}, route: {ok: complete, empty: retry}}
```

Routing mapping: graph-code `transitions.action` ↔ Graph-Lang control-port name; graph-code's `condition` ↔ the expression in `post.route`.

---

## 6. How Workflows Use Static Graphs (books, apps, knowledge bases)

Make the static layer a **first-class input and output of workflows**, instead of workflows building graph text ad hoc.

| Capability | Node | Behaviour | Risk |
|---|---|---|---|
| Read / slice / summarize a static graph | `QUERY` (already declared, currently a no-op) | args: file, dialect (auto-detected), operation (`load`, `slice(target)`, `order`, `gap`, `validate`); output: JSON subgraph or report | read-only |
| Validate a graph (gate) | `ASSERT`/`EXEC` calling `zinet validate --strict` | pass/fail edge | none |
| Write or update a static graph | `EMIT` (already declared, currently a no-op) | must pass `zinet validate` before write; writes go through the comment-preserving round trip; Cedar `GUARD` decides allowed paths | **risky**: already classed as risky in `topology.py` (`RISKY_TYPES = ("EMIT", "QUERY")`) |
| Diff against a prior version | `EXEC` calling `zinet diff` | change report | none |

These give the four things you want to build:
- **Book:** workflow generates concept graph (`GENERATE` constrained to the zinet/ConceptBook schema) → `validate --strict` gate → per-concept chapter generation via `LOOP` or batch fan-out over `learning_path` order. (The existing `concept_book` cookbook is a prose-only version of this; add the graph stage.)
- **App:** blueprint graph (graph-code) → `order` → per-component generate/test loop with `ASSERT` on the blueprint's `verification:` entries → drift report back into the blueprint's `blueprint.drift`.
- **Knowledge base:** work-graph layers updated by an ingest workflow; LLM-proposed nodes are written as `INFERRED` until confirmed (work-graph's own convention).
- **Workflow:** Graph-Lang graphs themselves, kept in the executable layer.

---

## 7. Work Items

Ordered; each has an acceptance test on **real files**, not toy examples.

| # | Item | Repo | Acceptance |
|---|---|---|---|
| M1 | Add `zinet.model` (§3.1): `GraphModel`/`NodeModel`/`EdgeModel`, `kind`, version, `to_networkx()` (dependency → dependent), plus the additive `EdgeType` values (`composed_of`, `control_flow`) and `optional` flag; `Graph ⇄ GraphModel` adapter. Write the edge registry (§3) into the module docstring/spec | zinet | all existing zinet tests pass unchanged; `Graph → GraphModel → Graph` round trip is lossless on zinet's own fixtures; JSON Schema for the model published; release `0.3.0` |
| M2 | Extend `zinet.formats.detect` with graph-code v2.x and add adapters for ConceptBook flat and graph-code `form` (readers; the ConceptBook writer keeps its original shape) | zinet | `cb-linalg/public/domains/graph.yaml` and `graph-code/apps/todo/blueprint/backend.graph.yaml` load into `GraphModel`; `zinet validate` runs on them; `zinet render` draws them; `explain_foreign` updated |
| M3 | *(folded into M1; the additive `EdgeType` change ships with the model)* | zinet | — |
| M4 | Graph-Lang adapter (`workflow` nodes/edges ⇄ `GraphModel`, ports preserved) so `zinet diff/slice` work on workflows; graflang depends on `zinet>=0.3` and `graphlang/formats.py` uses the new `detect` | zinet (adapter) + graflang (dependency bump) | `zinet slice` on `code_pipeline.graph.yaml` returns a node plus its prerequisites; a workflow round-trips `YAML → GraphModel → YAML` without changing node ids, ports or edges (comments preserved via `zinet.roundtrip`) |
| M5 | Adopt `phases: {pre, exec, post}` naming in Graph-Lang E1; document equivalence (`execute` ↔ `exec`) with graph-code workflow profile | graflang | design doc and schema updated; cross-dialect example included |
| M6 | graph-code workflow profile ⇄ Graph-Lang converter (both directions where lossless, flagged where not) | graflang or graph-code | `apps/etl_workflow.graph.yaml` converts to a runnable Graph-Lang graph on the `mock` adapter |
| M7 | Implement `QUERY` (read/slice/validate/order a static graph) and a gated `EMIT` (write after `zinet validate`), plus Cedar policy for write paths | graflang | a cookbook workflow reads a ConceptBook graph and emits a validated update |
| M8 | **Freeze rule:** any new field or dialect must add a row to §2 and a registry entry before merging | all | review checklist item |

---

## 8. Open Questions

1. ~~**Where does the shared model live?**~~ **Resolved: zinet** (`zinet.model`, §3.1). It is additive and separate from the zinet-dialect file format (`zinet.schema.Graph`, which keeps `extra="forbid"` and the three layers), so the strict file validation is unaffected. Remaining sub-question: how much port information the model carries for static graphs (proposal: `ports` optional, ignored by static tools).
2. **Two workflow forms:** graph-code's `workflow` profile and Graph-Lang overlap. Long term, should graph-code workflows be *authored* in Graph-Lang and only *represented* in graph-code for drift/blueprint tracking?

[WEN] graph-code is still in dev stage, can change, we should develop GraphLang first, once done, graph-code will be simplified. graph-code has a module called "ide" used to edit graph .yaml, you could review and migrate into GraphLang (graflang)

3. **Data edges in graph-code workflows:** transitions carry no ports. Acceptable for conversion to be lossy there, or add optional `data` bindings to transitions?

[WEN] leave graph-code alone, once graflang is stable, we will refactor graph-code significantly

4. **work-graph:** layers are JSON-canonical with a YAML review format. Is it in scope for the shared model now, or after M1–M4?

[WEN] work-graph is also in early dev stage, we focus on stablizing graflang first, then refactor work-graph

5. **ConceptBook freeze:** it is frozen while its paper is in progress. The M2 reader does not require changing `cb-*` repos, which keeps within that freeze.

[WEN] yes, leave ConceptBook alone, once graflang is stable and after conceptbook paper is out, we will refactor it according to zinet/graflang codebases
