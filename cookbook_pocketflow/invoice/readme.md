# 031 — Invoice Processor  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/031_invoice` with `spl3 util spl2graph` (AST-direct, no model involved); source `invoice.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-invoice](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-invoice)
**Difficulty:** ★★☆
**Category:** document-intelligence

## What it does

Extracts structured data from PDF invoices and validates the extracted math before committing the result. A deterministic PDF reader converts the invoice to text, the LLM extracts all fields (vendor, customer, line items, tax, total) as a JSON object, a deterministic math validator computes the expected total from line items and compares it against the declared total, and the workflow flags the invoice as valid or invalid based on the check. No hallucinated totals pass undetected.

## Real-world use cases

- **Accounts payable automation**: Process incoming supplier invoices at scale, catching math discrepancies before they reach the payment queue
- **Expense report auditing**: Extract and validate line items from submitted receipts, flagging anything where the total doesn't reconcile with the line item sum
- **Three-way matching**: Combine invoice extraction with purchase-order and goods-receipt data for automated procurement reconciliation
- **Regulatory compliance**: Maintain an audit trail of machine-extracted and math-validated invoice data without manual data entry error

## Key SPL constructs

- `CREATE TOOL_API load_pdf_invoice(pdf_path)` — extracts text from a PDF using pypdf
- `CREATE FUNCTION extract_invoice_fields(pdf_content)` — LLM extracts all invoice fields as a strict JSON schema
- `CREATE TOOL_API parse_invoice_json(raw_json)` — strips code fences and parses the JSON
- `CREATE TOOL_API validate_invoice_math(invoice_json)` — deterministic sum check: line_items + tax vs. declared total; returns "pass" or a detailed failure string
- `CREATE TOOL_API build_invoice_output(invoice_json, status, notes)` — attaches `validation_status` and `validation_notes` to the extracted JSON
- `EVALUATE @math_check WHEN contains("pass")` — routes to "valid" vs. "invalid" output

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@pdf_path` | TEXT | `"invoice.pdf"` | Path to the invoice PDF to process |

**Output:** `@result TEXT` — the extracted invoice JSON with `validation_status` ("valid" or "invalid") and `validation_notes` on failure

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/invoice/invoice.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `WHILE` self-repair loop that feeds the math validation error back to the LLM to re-extract the offending field
- Extend `extract_invoice_fields` to capture additional fields (payment terms, bank details, PO number) without changing the validation logic
- Chain multiple PDF invoices with `WHILE @i < @count DO` to batch-process an entire inbox of invoices
- Add a downstream `CALL post_to_erp(@result)` tool to push validated invoices directly into an ERP or accounting system
