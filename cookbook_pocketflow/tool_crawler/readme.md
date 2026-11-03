# 058 — Tool Crawler (Web Crawler)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/058_tool_crawler` with `spl3 util spl2graph` (AST-direct, no model involved); source `tool_crawler.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tool-crawler](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tool-crawler)
**Difficulty:** —
**Category:** tool-use

## What it does

A domain-scoped web crawler: starting from a seed URL, the workflow fetches pages, extracts text and same-domain links, filters out already-visited and already-queued URLs, and adds new links to the crawl queue — iterating in a WHILE loop until the page budget is exhausted or the queue is empty. Extracted page text is accumulated for downstream use. All crawl-state management (queue, visited set) uses deterministic tools over `|||`-delimited string lists.

## Real-world use cases

- **Documentation indexing**: Crawl a product documentation site to collect all pages for embedding or search indexing
- **Competitive intelligence**: Crawl a competitor's public site to extract product pages, pricing information, or blog content for analysis
- **Link graph analysis**: Collect the link structure of a site for SEO analysis, broken link detection, or site architecture review
- **Dataset collection**: Crawl a domain-constrained set of pages to build a training corpus for domain-specific LLM fine-tuning

## Key SPL constructs

- `CREATE TOOL_API extract_domain(url)` — parses the domain from the seed URL for domain scoping
- `CREATE TOOL_API extract_text_and_links(html, base_url, domain)` — strips HTML tags, extracts visible text, and collects same-domain absolute URLs
- `CREATE TOOL_API queue_pop_url(queue)` / `queue_remove_first(queue)` — FIFO queue operations over `|||`-delimited strings
- `CREATE TOOL_API visited_add(visited, url)` — adds a URL to the visited set
- `CREATE TOOL_API filter_new_links(links, visited, queue, domain)` — deduplicates new links against visited and queued sets
- `CALL fetch_url(@current_url)` — fetches raw HTML from the current URL
- `WHILE @page_count < @max_pages AND @queue_empty = "false" DO` — crawl loop

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@seed_url` | TEXT | _(required)_ | Starting URL for the crawl |
| `@max_pages` | INTEGER | 20 | Maximum number of pages to crawl |

**Output:** `@all_text TEXT` — concatenated extracted text from all crawled pages

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/tool_crawler/tool_crawler.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `GENERATE summarize_page(@text)` step for each page to produce per-page summaries alongside the raw text
- After crawling, feed `@all_text` into `060_tool_embeddings` to build a searchable vector index of the site
- Add a `CALL write_file(@output_file, @page_text + "\n---\n", "a")` step inside the loop to stream results to disk for large crawls
- Parameterize with `--param seed_url=https://example.com --param max_pages=50` for targeted crawls without editing the .spl
