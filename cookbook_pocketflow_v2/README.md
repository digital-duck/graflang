# cookbook_pocketflow_v2: PocketFlow recipes in the layered form

Recipes of `cookbook_pocketflow/` (SPL.py's `cookbook-pocketflow`, lifted with `spl2graph`) rewritten with composites. The originals stay as they are. These recipes differ in shape (a fork and a
join, a retry loop, a tool chain), so each one's groups were chosen by hand with `scripts/port_recipe.py`; every step is named after the tool or prompt it runs.

| Recipe | Original | Composites |
|---|---|---|
| [`debate`](debate) | `cookbook_pocketflow/debate` | `opening` |
| [`majority_vote`](majority_vote) | `cookbook_pocketflow/majority_vote` | `tally`, `vote` |
| [`rag`](rag) | `cookbook_pocketflow/rag` | `deliver`, `index`, `retrieve` |
| [`self_healing`](self_healing) | `cookbook_pocketflow/self_healing` | `draft` |

Each recipe's `readme.md` is the original's with a layered-port note on top; the `.spl` source is kept beside the graph. A retry loop is still one box at the top level (open it with
`graf vis --depth 1`).

Not yet ported (37): the other recipes of `cookbook_pocketflow/`. Those whose loop is not compactable (`judge`, `supervisor`, `text2sql`, `map_reduce`) keep part of the graph in long form, which
`scripts/port_recipe.py` handles, but their groups need choosing; `chat` and `cli_hitl` wait for keyboard input.

## Port one

```bash
python scripts/port_recipe.py pocketflow NAME --list                       # the steps, named: choose groups from this
python scripts/port_recipe.py pocketflow NAME part=step,step part2=step    # graf group, in this order; the result is validated
pytest tests/test_cookbook_pocketflow_v2.py -q
```

## Checked

`tests/test_cookbook_pocketflow_v2.py`: every graph validates with no errors or warnings, has composites and a short top level, and gives the same outputs as its original on the mock adapter with
default inputs (temporary file names masked). Not checked: a real model's answers.
