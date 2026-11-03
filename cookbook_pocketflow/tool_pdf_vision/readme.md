# 061 — Tool PDF Vision (OCR Pipeline)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/061_tool_pdf_vision` with `spl3 util spl2graph` (AST-direct, no model involved); source `tool_pdf_vision.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tool-pdf-vision](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tool-pdf-vision)
**Difficulty:** —
**Category:** tool-use

## What it does

A vision-based PDF OCR pipeline: scans a directory for PDF files, converts each page to a 200-DPI PNG image using `pdf2image`, and then uses a multimodal LLM GENERATE call to extract and reformat the visible text as clean Markdown — preserving headings, lists, tables, and paragraphs as they appear on the page. Nested WHILE loops iterate over PDFs and pages, accumulating a combined Markdown output file.

## Real-world use cases

- **Scanned document digitization**: Convert scanned PDFs (where text extraction fails) into searchable, editable Markdown by using a vision LLM for OCR rather than a text parser
- **Legal document processing**: Extract text from PDF contracts, court filings, or regulatory documents that were scanned or image-rendered
- **Research paper ingestion**: Convert academic PDFs with complex two-column layouts, mathematical notation, and figures into clean Markdown for downstream analysis
- **Archival digitization**: Process historical document archives where the PDFs contain scanned images rather than embedded text

## Key SPL constructs

- `CREATE TOOL_API scan_pdfs(input_dir)` — globs all `*.pdf` files recursively and returns a comma-delimited list
- `CREATE TOOL_API pdf_to_images(pdf_path, work_dir)` — uses `pdf2image.convert_from_path` at 200 DPI, writes PNGs to a per-PDF subdirectory
- `CREATE FUNCTION ocr_page_to_markdown(image_path)` — multimodal GENERATE call: the LLM is instructed to read the page image and return clean Markdown
- Outer `WHILE @pdf_idx < @max_pdfs DO` — iterates over PDF files
- Inner `WHILE @page_idx < @max_pages DO` — iterates over pages of each PDF
- `CALL write_file(@output_file, @combined_markdown, "w")` — writes the accumulated Markdown to the output file

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@input_dir` | TEXT | `"./pdfs"` | Directory to scan for PDF files |
| `@output_file` | TEXT | `"./output.md"` | Path to write the combined Markdown output |
| `@work_dir` | TEXT | `"/tmp/pdf_ocr_work"` | Working directory for intermediate PNG files |
| `@max_pdfs` | INTEGER | 100 | Maximum number of PDFs to process |
| `@max_pages` | INTEGER | 1000 | Maximum number of pages across all PDFs |

**Output:** `@combined_markdown TEXT` — the full concatenated Markdown from all processed PDF pages

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/tool_pdf_vision/tool_pdf_vision.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add `CALL PARALLEL` to process multiple pages of the same PDF simultaneously, with ordered merging after the parallel block
- Chain with `060_tool_embeddings` to embed each page's Markdown for a searchable vector index of scanned documents
- Add a `GENERATE summarize_document(@page_texts)` step after each PDF to produce a document-level summary alongside the raw OCR
- Replace the work_dir cleanup with a caching step: skip re-conversion if PNGs already exist for faster re-runs on unchanged files
