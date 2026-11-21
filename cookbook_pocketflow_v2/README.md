# cookbook_pocketflow_v2: PocketFlow recipes in the layered form

8 of the 41 recipes of `cookbook_pocketflow/` (SPL.py's `cookbook-pocketflow`, lifted with `spl2graph`) rewritten with composites. The originals stay as they are. These recipes differ in shape (a fork
and a join, a tool chain, a retry loop), so each one's groups were chosen by hand with `scripts/port_recipe.py`; every step is named after the tool or prompt it runs.

| Recipe | Original | Composites |
|---|---|---|
| [`agent_skills`](agent_skills) | `cookbook_pocketflow/agent_skills` | `apply`, `find_skills` |
| [`batch`](batch) | `cookbook_pocketflow/batch` | `languages`, `translate` |
| [`debate`](debate) | `cookbook_pocketflow/debate` | `opening` |
| [`invoice`](invoice) | `cookbook_pocketflow/invoice` | `extract` |
| [`majority_vote`](majority_vote) | `cookbook_pocketflow/majority_vote` | `tally`, `vote` |
| [`mcp`](mcp) | `cookbook_pocketflow/mcp` | `plan` |
| [`rag`](rag) | `cookbook_pocketflow/rag` | `deliver`, `index`, `retrieve` |
| [`self_healing`](self_healing) | `cookbook_pocketflow/self_healing` | `draft` |

Each recipe's `readme.md` is the original's with a layered-port note on top; the `.spl` source is kept beside the graph. A retry loop is still one box at the top level (open it with `graf vis --depth 1`).

**Not ported (33):** most of the rest are a retry loop (an agent, a debate round, a crawler, a thinking loop) around a few set-up steps: the loop is already one box at the top level, and what is left
to group is bookkeeping (`set_*` steps), so layering them adds no meaning. Others are very small (`tool_database`, `tool_embeddings`, `tool_search`, `visualization`: 3 to 6 steps), have two steps that both start from
the input so no group has a single entry (`structured_output`), or wait for keyboard input (`chat`, `cli_hitl`).

## Port one

```bash
python scripts/port_recipe.py pocketflow NAME --list                       # the steps, named: choose groups from this
python scripts/port_recipe.py pocketflow NAME part=step,step part2=step    # graf group, in this order; the result is validated
pytest tests/test_cookbook_pocketflow_v2.py -q
```

## Checked

`tests/test_cookbook_pocketflow_v2.py`: every graph validates with no errors or warnings, has composites and a short top level, and gives the same outputs as its original on the mock adapter with
default inputs (temporary file names, node and procedure names in messages masked, a mock procedure's inputs compared as a set). A recipe that cannot finish there (`agent_skills` needs a real answer to name
a file) must fail the same way in both. Not checked: a real model's answers.
