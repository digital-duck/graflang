# 013 — Batch Flow  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/013_batch_flow` with `spl3 util spl2graph` (AST-direct, no model involved); source `batch_text_transformer.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-batch-flow](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-batch-flow)
**Difficulty:** ★☆☆
**Category:** basics

## What it does

Applies a multi-step image transformation workflow to an entire batch of images, iterating over every combination of image and filter via nested WHILE loops. For each (image, filter) pair, a deterministic `apply_image_filter` tool performs the transformation (grayscale, blur, or sepia) and writes the output to a designated directory. This demonstrates how SPL's WHILE-based batch iteration cleanly replaces Python's explicit for-loop comprehensions.

## Real-world use cases

- **Digital asset management**: Apply consistent brand filters to batches of marketing images or product photos across an e-commerce catalog
- **Medical imaging preprocessing**: Normalize and transform scan images (contrast adjustment, denoising) before feeding them into downstream ML models
- **Content moderation pipelines**: Apply grayscale or blur transformations to potentially sensitive images before human review
- **Photography workflow automation**: Process event or real estate photos through multiple stylistic filters to generate variants for client selection

## Key SPL constructs

- `CREATE TOOL_API apply_image_filter(image_path, filter_name, output_dir)` — applies grayscale, blur, or sepia; writes output file; returns `"ok: /path/to/output"`
- `WHILE @i < @max_images DO` — outer loop over image list
- `WHILE @j < @max_filters DO` — inner loop over filter list
- `CALL list_get(@images, @i, ",")` — comma-delimited list indexing
- `CALL make_dir(@output_dir)` — ensures output directory exists before writes
- Log accumulation into `@log` across the nested loops

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@images` | TEXT | `"img1.jpg,img2.jpg,img3.jpg"` | Comma-delimited list of image paths |
| `@filters` | TEXT | `"grayscale,blur,sepia"` | Comma-delimited list of filter names to apply |
| `@max_images` | INTEGER | 3 | Upper bound on number of images |
| `@max_filters` | INTEGER | 3 | Upper bound on number of filters |
| `@output_dir` | TEXT | `"output/"` | Directory to write transformed images |

**Output:** `@log TEXT` — newline-delimited log of each `(image, filter) → output_path` result

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/batch_flow/batch_text_transformer.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `GENERATE caption_image(@output_path)` step after each filter to produce alt text for each transformed image
- Replace the inner filter loop with `CALL PARALLEL` to apply all filters to a single image simultaneously
- Wire `--adapter momagrid` to distribute each outer-loop iteration across Momagrid worker nodes
- Add `EXCEPTION WHEN` handling for corrupt or unreadable input images so the batch continues past failures
