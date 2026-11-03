# 064 — Visualization (Order Fulfillment Pipeline)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/064_visualization` with `spl3 util spl2graph` (AST-direct, no model involved); source `visualization.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-visualization](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-visualization)
**Difficulty:** —
**Category:** basics

## What it does

Implements a multi-stage order fulfillment pipeline as three composable sub-workflows chained by `CALL`: payment validation and processing (with retry loop), inventory check and reservation, and carrier assignment for shipping — assembled into a top-level `order_fulfillment` workflow. Each sub-workflow writes its result to a named JSON file and returns a structured status. This demonstrates workflow composition via `CALL` and the separation of concerns across independently reusable WORKFLOW and PROCEDURE units.

## Real-world use cases

- **E-commerce order processing**: Run payment capture, inventory reservation, and shipment creation as a single atomic-feeling pipeline from a checkout event
- **B2B procurement automation**: Automate multi-step procurement workflows — PO approval, inventory check, supplier order — as composable sub-workflows
- **Event-driven fulfillment**: Use each sub-workflow as an independently deployable step that can be reused across order types (digital goods, physical goods, subscriptions)
- **Workflow visualization demo**: The clean `CALL`-based composition makes this an ideal workflow to visualize in the SPL Mermaid diagram output (`spl3 splc --target mermaid`)

## Key SPL constructs

- `WORKFLOW payment_workflow` — validates payment fields deterministically + processes with retry loop (WHILE + EVALUATE); writes `payment_status.json`
- `WORKFLOW inventory_workflow` — checks stock availability + reserves items; writes `inventory_status.json`
- `WORKFLOW shipping_workflow` — creates a shipment and assigns a carrier; writes `shipping_status.json`
- `WORKFLOW order_fulfillment` — top-level orchestrator: `CALL payment_workflow → CALL inventory_workflow → CALL shipping_workflow → build_order_status`
- `CREATE TOOL_API validate_payment(order_data)` — deterministic regex/range validation of card number, expiry, CVV, and amount
- `CREATE TOOL_API process_payment(order_data)` — simulates payment capture; returns `{"status": "success", "transaction_id": ...}`
- `CALL json_get(@inventory_result, "reservation_id")` — extracts the reservation ID to pass to the shipping sub-workflow

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@order_data` | TEXT | _(required)_ | JSON object with `payment` (card details, amount) and `items` (availability, reservation info) |
| `@max_payment_retries` | INTEGER | 3 | Maximum payment processing retry attempts |

**Output:** `@order_status TEXT` — JSON object combining payment, inventory, and shipping results

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/visualization/visualization.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Run `spl3 splc cookbook-pocketflow/064_visualization/visualization.spl --target mermaid` to generate a workflow diagram that visualizes the sub-workflow composition
- Add `EXCEPTION WHEN WorkflowCompositionError` handling in `order_fulfillment` to capture payment or inventory failures and trigger a refund sub-workflow
- Use `--adapter momagrid` to dispatch `payment_workflow`, `inventory_workflow`, and `shipping_workflow` to separate Momagrid worker nodes for true microservice isolation
- Replace the simulated `process_payment` tool with a real payment gateway integration (Stripe, Braintree) to deploy as a production payment pipeline
