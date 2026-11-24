"""`graf util`: conversion and document helpers (ported from `spl3 util`).

Self-contained here (no SPL runtime needed): clean-port, html2pdf, md2pdf, mmd2img.
Delegated to spl3 when you run them (`pip install 'graflang[spl]'`): the commands that read or write SPL source or use spl3's LLM
adapters: describe, explain, graph2spl, img2mmd, img2text, mmd2spl, spl2graph, spl2mmd, text2mmd. They are listed here, and `graf util NAME -h`
shows spl3's own help for them.
"""
from __future__ import annotations

import click
from zinet.click_helpers import HELP_OPTION_NAMES, FullHelpGroup

# name -> one-line help, for the commands that live in spl3 (so `graf util -h` can list them without importing spl3)
DELEGATED = {
    "describe": "Generate a plain-English spec for an .spl file or folder.",
    "explain": "Show execution plan for an .spl file (no LLM call).",
    "graph2spl": "Rebuild SPL source from a GraphLang *.graph.yaml.",
    "img2mmd": "Extract a Mermaid flowchart from an image.",
    "img2text": "Extract text and pseudo-code from an image.",
    "mmd2spl": "Generate SPL workflow from Mermaid flowchart diagram.",
    "spl2graph": "Lift each .spl workflow into a GraphLang *.graph.yaml.",
    "spl2mmd": "Generate a Mermaid flowchart for each .spl file.",
    "text2mmd": "Generate a Mermaid flowchart from natural language.",
}


def _spl3_command(name: str) -> click.Command:
    try:
        from spl3.cli import cmd_util
    except ImportError as exc:
        raise click.ClickException(f"`graf util {name}` runs spl3's implementation; install it with: pip install 'graflang[spl]'  ({exc})")
    return cmd_util.commands[name]


class UtilGroup(FullHelpGroup):
    """`graf util`: own commands plus the DELEGATED ones, which load spl3 only when one is run."""

    def list_commands(self, ctx):
        return sorted(set(super().list_commands(ctx)) | set(DELEGATED))

    def get_command(self, ctx, name):
        return super().get_command(ctx, name) or (_spl3_command(name) if name in DELEGATED else None)

    def format_commands(self, ctx, formatter):
        rows = []
        for name in self.list_commands(ctx):
            own = super().get_command(ctx, name)
            if own is not None and own.hidden:
                continue
            text = (own.short_help or (own.help or "").split("\n\n")[0]) if own is not None else DELEGATED[name]
            rows.append((name, " ".join(text.split())))
        with formatter.section("Commands"):
            formatter.write_dl(rows)


@click.group("util", cls=UtilGroup, context_settings={"help_option_names": HELP_OPTION_NAMES},
             short_help="Format conversion, document tools, and one-off helpers.")
def util() -> None:
    """Utility commands: format conversion (Markdown/HTML to PDF, Mermaid to image, SPL and GraphLang), document tools, helpers."""


# ---- html2pdf (logic in grafu/html2pdf.py) -------------------------------------------------------------------------------------------

@util.command("html2pdf", short_help="Convert an .html slide deck (or page) to .pdf with headless Chromium.")
@click.argument("html_file", metavar="HTML_FILE")
@click.option("-o", "--output", default=None, metavar="PDF", help="Output file (default: next to the input, same name, .pdf).")
@click.option("--browser", default=None, metavar="NAME",
              help="Chromium or Chrome to use: a name on PATH or a path (default: $CHROME, else the first found).")
@click.option("--timeout", default=120, show_default=True, help="Seconds to wait for the browser.")
def cmd_html2pdf(html_file, output, browser, timeout):
    """Convert an .html slide deck to a .pdf (no LLM).

    Uses the page's own print stylesheet (@page size, one slide per page, backgrounds kept), so the
    result matches the deck's browser Print > Save as PDF with Background graphics on.

    \b
    Examples:
      graf util html2pdf docs/DEMO/graflang-intro.html
      graf util html2pdf deck.html -o deck-20261103.pdf
    """
    from pathlib import Path
    from .html2pdf import Html2PdfError, count_pages, html_to_pdf

    try:
        out = html_to_pdf(Path(html_file), Path(output) if output else None, browser=browser, timeout=timeout)
    except Html2PdfError as exc:
        click.echo(f"FAILED: {exc}", err=True)
        raise SystemExit(1)
    click.echo(f"{out.resolve()}  ({count_pages(out)} pages)")


# ---- clean-port, mmd2img, md2pdf (copied from spl3 util) -----------------------------------------------------------------------------

def _parse_port_spec(spec: str) -> list[int]:
    """Parse a comma-separated port/range spec into a sorted list of ports.

    Accepts individual ports and inclusive ranges, freely mixed and spaced,
    e.g. "8000, 8001, 8010 - 8020". Raises ValueError on anything that
    doesn't parse as an int (or int-int) after stripping whitespace.
    """
    ports: set[int] = set()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        if "-" in token:
            lo_s, hi_s = (t.strip() for t in token.split("-", 1))
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                lo, hi = hi, lo
            ports.update(range(lo, hi + 1))
        else:
            ports.add(int(token))
    return sorted(ports)


def _pids_on_port(port: int) -> list[int]:
    """Return PIDs of processes with a listening socket on `port` (Linux/macOS)."""
    import subprocess
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        raise click.ClickException(
            "clean-port requires 'lsof' on PATH (present by default on macOS "
            "and most Linux distros)."
        )
    return [int(p) for p in result.stdout.split() if p.strip()]


@util.command("clean-port", short_help="Kill whatever process is listening on given ports.")
@click.argument("ports")
@click.option("--force", "-9", is_flag=True, default=False,
              help="Send SIGKILL instead of SIGTERM.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be killed without killing anything.")
def cmd_clean_port(ports: str, force: bool, dry_run: bool) -> None:
    """Kill whatever process is listening on each given port.

    PORTS is a comma-separated list of ports and/or inclusive ranges:

    \b
        graf util clean-port "8319"
        graf util clean-port "8319, 8219"
        graf util clean-port "8319, 8219, 9000-9010"

    Stray dev servers (vite, uvicorn --reload, ...) are the usual target —
    this is a plain "whatever owns this port, kill it" hammer, not aware of
    what the process actually is.
    """
    import os
    import signal

    try:
        port_list = _parse_port_spec(ports)
    except ValueError:
        raise click.ClickException(f"Could not parse port spec: {ports!r}")
    if not port_list:
        click.echo("No ports given.")
        return

    sig = signal.SIGKILL if force else signal.SIGTERM
    any_killed = False
    for port in port_list:
        pids = _pids_on_port(port)
        if not pids:
            click.echo(f"  port {port}: nothing listening")
            continue
        for pid in pids:
            if dry_run:
                click.echo(f"  port {port}: would kill PID {pid} ({sig.name})")
                continue
            try:
                os.kill(pid, sig)
                click.echo(f"  port {port}: killed PID {pid} ({sig.name})")
                any_killed = True
            except ProcessLookupError:
                click.echo(f"  port {port}: PID {pid} already gone")
            except PermissionError:
                click.echo(f"  port {port}: no permission to kill PID {pid} (try sudo)")

    if dry_run:
        click.echo("(dry run — nothing was actually killed)")
    elif not any_killed:
        click.echo("Nothing was killed.")


def _mmd_single_html(mmd_text: str, title: str) -> str:
    """Standalone HTML page that renders one mermaid diagram."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body{{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5}}
    .container{{max-width:1400px;margin:0 auto;background:white;padding:20px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1)}}
    .mermaid{{text-align:center;margin:20px 0}}
    pre{{background:#f8f9fa;border:1px solid #e9ecef;border-radius:4px;padding:15px;font-family:monospace;white-space:pre-wrap}}
  </style>
</head>
<body>
  <div class="container">
    <h2>{title}</h2>
    <div class="mermaid">{mmd_text}</div>
    <details style="margin-top:20px"><summary style="cursor:pointer;color:#57606a">Source</summary>
      <pre>{mmd_text}</pre></details>
  </div>
  <script>mermaid.initialize({{startOnLoad:true,theme:'default',securityLevel:'loose',errorLevel:'warn'}});</script>
</body>
</html>"""


@util.command("mmd2img", short_help="Convert a .mmd Mermaid file to PNG/SVG/PDF/HTML.")
@click.argument("mmd_files", nargs=-1, required=True, metavar="MMD_FILE...")
@click.option("--format", "-f", "fmt",
              default="png", show_default=True,
              type=click.Choice(["png", "svg", "pdf", "html"], case_sensitive=False),
              help="Output format.")
@click.option("--out", "-o", default=None, metavar="FILE",
              help="Output file path (single input only).")
@click.option("--out-dir", default=None, metavar="DIR",
              help="Output directory (default: same directory as each input file).")
@click.option("--background", default="white", show_default=True,
              help="Background colour for PNG/SVG (e.g. white, transparent).")
@click.option("--theme", default="default", show_default=True,
              type=click.Choice(["default", "forest", "dark", "neutral"]),
              help="Mermaid theme.")
@click.option("--width", "-w", default=None, type=int, metavar="PX",
              help="Output width in pixels (PNG/SVG only). mmdc default: 800.")
@click.option("--height", "-H", default=None, type=int, metavar="PX",
              help="Output height in pixels (PNG/SVG only). mmdc default: auto.")
def cmd_mmd2img(mmd_files, fmt, out, out_dir, background, theme, width, height):
    """Convert one or more Mermaid .mmd files to an image.

    Uses mmdc (Mermaid CLI) if installed; otherwise falls back to
    'npx --yes @mermaid-js/mermaid-cli' (requires Node.js).

    HTML output uses the built-in renderer (no mmdc required).

    \b
    Install mmdc once:
      npm install -g @mermaid-js/mermaid-cli

    \b
    Examples:
      graf util mmd2img diagram.mmd                      # → diagram.png
      graf util mmd2img diagram.mmd -f svg               # → diagram.svg
      graf util mmd2img diagram.mmd -o /tmp/out.png      # explicit path
      graf util mmd2img *.mmd --out-dir ./images         # batch convert
      graf util mmd2img diagram.mmd -f pdf --theme dark
      graf util mmd2img diagram.mmd -f html              # no mmdc needed
      graf util mmd2img diagram.mmd -w 1800 -H 900       # custom dimensions
    """
    import shutil, subprocess, json, tempfile
    from pathlib import Path

    if out and len(mmd_files) > 1:
        raise click.UsageError("--out/-o can only be used with a single input file.")

    mmdc = shutil.which("mmdc")
    mmdc_base = [mmdc] if mmdc else ["npx", "--yes", "@mermaid-js/mermaid-cli"]

    puppet_cfg = Path(tempfile.mktemp(suffix=".json"))
    puppet_cfg.write_text(json.dumps({"args": ["--no-sandbox"]}))

    try:
        for mmd_file in mmd_files:
            mmd_path = Path(mmd_file)
            if not mmd_path.exists():
                click.echo(f"Warning: {mmd_file} not found — skipped", err=True)
                continue

            if fmt == "html":
                mmd_text = mmd_path.read_text(encoding="utf-8")
                if out:
                    out_path = Path(out)
                elif out_dir:
                    out_path = Path(out_dir) / f"{mmd_path.stem}.html"
                else:
                    out_path = mmd_path.with_suffix(".html")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(_mmd_single_html(mmd_text, mmd_path.stem), encoding="utf-8")
                click.echo(f"HTML: {out_path}")
                continue

            # PNG / SVG / PDF — via mmdc
            if out:
                out_path = Path(out)
            elif out_dir:
                out_path = Path(out_dir) / f"{mmd_path.stem}.{fmt}"
            else:
                out_path = mmd_path.with_suffix(f".{fmt}")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            args = mmdc_base + [
                "-i", str(mmd_path),
                "-o", str(out_path),
                "-p", str(puppet_cfg),
                "--backgroundColor", background,
                "--theme", theme,
            ]
            if width is not None and fmt in ("png", "svg"):
                args += ["-w", str(width)]
            if height is not None and fmt in ("png", "svg"):
                args += ["-H", str(height)]
            try:
                r = subprocess.run(args, capture_output=True, timeout=60)
                if r.returncode == 0:
                    click.echo(f"{fmt.upper()}: {out_path}")
                else:
                    stderr = r.stderr.decode(errors="replace").strip()
                    click.echo(f"Error rendering {mmd_path.name}:", err=True)
                    if stderr:
                        click.echo(f"  {stderr}", err=True)
                    click.echo("  Install mmdc: npm install -g @mermaid-js/mermaid-cli", err=True)
            except FileNotFoundError:
                raise click.ClickException(
                    "mmdc not found and npx is unavailable.\n"
                    "Install: npm install -g @mermaid-js/mermaid-cli"
                )
            except subprocess.TimeoutExpired:
                click.echo(f"Warning: mmdc timed out for {mmd_path.name}", err=True)
    finally:
        puppet_cfg.unlink(missing_ok=True)


@util.command("md2pdf", short_help="Convert a Markdown file to PDF via pandoc + XeLaTeX.")
@click.argument("md_file", metavar="MD_FILE")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Output PDF path (default: same directory as input, same stem).")
@click.option("--font", default="DejaVu Serif", show_default=True,
              help="Body font name (must be installed on the system).")
@click.option("--mono-font", default="DejaVu Sans Mono", show_default=True,
              help="Monospace font for code blocks.")
@click.option("--font-size", default="11pt", show_default=True,
              help="Base font size (e.g. 10pt, 12pt).")
@click.option("--margin", default="0.75in", show_default=True,
              help="Page margin (e.g. 1in, 2cm).")
@click.option("--toc/--no-toc", default=True, show_default=True,
              help="Include a table of contents.")
@click.option("--toc-depth", default=2, show_default=True, type=int,
              help="TOC depth (number of heading levels to include).")
@click.option("--h-lines/--no-h-lines", default=True, show_default=True,
              help="Draw horizontal grid lines between every table row.")
@click.option("--v-lines/--no-v-lines", default=True, show_default=True,
              help="Draw vertical grid lines between every table column.")
def cmd_md2pdf(md_file, output, font, mono_font, font_size, margin, toc, toc_depth,
               h_lines, v_lines):
    """Convert a Markdown file to PDF using pandoc + XeLaTeX.

    Handles Unicode, box-drawing characters, and local image paths.
    Tables get full grid lines (horizontal + vertical) by default; use
    --no-h-lines / --no-v-lines to drop either axis.
    Requires pandoc and a XeLaTeX installation (e.g. texlive-xetex).

    \b
    Examples:
      graf util md2pdf docs/solver-guide.md
      graf util md2pdf report.md -o /tmp/report.pdf --no-toc
      graf util md2pdf spec.md --font "Liberation Serif" --font-size 12pt
      graf util md2pdf big-table.md --no-v-lines
    """
    import subprocess
    import tempfile
    from pathlib import Path

    md_path = Path(md_file).resolve()
    if not md_path.exists():
        raise click.ClickException(f"File not found: {md_path}")

    if output:
        out_path = Path(output).resolve()
    else:
        out_path = md_path.with_suffix(".pdf")

    click.echo(f"Input:  {md_path}", err=True)
    click.echo(f"Output: {out_path}", err=True)

    # Lua filter: reassign table column widths from actual content length.
    # Pandoc's default uses separator-dash counts (|:---:| = 5 dashes → ~45%
    # for a 3-column table) which ignores content — short columns bloat,
    # long-text columns overflow. This filter measures each column's content
    # two ways: total text length (for proportional distribution) and the
    # longest single unbreakable "word" (for a hard minimum) — a column
    # holding short terms like "ChromaDB" or "case_profile.json" has a tiny
    # total length but still needs enough width to fit that one token,
    # otherwise LaTeX can't hyphenate it and it overflows into the next
    # column instead of wrapping. Widths are clamped 4%-60%, then
    # renormalised so the sum <= 0.98.
    #
    # FULL_WIDTH_CHARS estimates how many characters fit across the full
    # table width, derived from this document's margin/font-size, so the
    # word-length minimum converts to a width fraction. The estimate is
    # deliberately conservative (fewer chars per line than a typical serif
    # font would fit) so narrow columns get a bit more room rather than less.
    try:
        _margin_in = float(margin.rstrip("in")) if margin.endswith("in") else \
            float(margin.rstrip("cm")) / 2.54
    except ValueError:
        _margin_in = 0.75
    try:
        _font_pt = float(font_size.rstrip("pt"))
    except ValueError:
        _font_pt = 11.0
    _text_width_in = max(3.0, 8.5 - 2 * _margin_in)
    _chars_per_inch = 120.0 / _font_pt
    _full_width_chars = max(40, round(_text_width_in * _chars_per_inch))
    # Column widths are computed as fractions of \linewidth, but LaTeX also
    # spends 2*tabcolsep of real width on EVERY column for its own left/right
    # cell padding -- overhead the width algorithm must budget for or a
    # many-column table silently overflows past the page's right margin.
    # Reducing tabcolsep (default 6pt) claws back some of that budget too.
    _tabcolsep_pt = 3.0
    _tabcolsep_in = _tabcolsep_pt / 72.27

    _LUA_AUTO_TABLE_WIDTHS = """\
local FULL_WIDTH_CHARS = __FULL_WIDTH_CHARS__
local TEXT_WIDTH_IN = __TEXT_WIDTH_IN__
local TABCOLSEP_IN = __TABCOLSEP_IN__
local GRID_H = __GRID_H__
local GRID_V = __GRID_V__

-- blocks is a plain Lua list of Block elements (Cell.content on new-AST
-- pandoc, or a table cell directly on pre-1.22 pandoc). stringify only
-- accepts a single AST element, not a bare list, so process block by block.
-- Returns total text length and the length of the longest whitespace-
-- delimited token (an approximation of what LaTeX cannot hyphenate/wrap).
local function col_stats(blocks)
  local total = 0
  local longest_word = 0
  for _, block in ipairs(blocks) do
    local text = pandoc.utils.stringify(block)
    total = total + #text
    for word in text:gmatch("%S+") do
      if #word > longest_word then longest_word = #word end
    end
  end
  return total, longest_word
end

local function compute_widths(n, totlen, maxword)
  -- Every column costs 2*tabcolsep of real width beyond its p{} content box
  -- (its own left+right cell padding), so the fraction-of-\linewidth budget
  -- has to shrink as column count grows, or wide tables overflow the page
  -- margin regardless of how well the per-column widths below are chosen.
  local overhead_frac = (2 * n * TABCOLSEP_IN) / TEXT_WIDTH_IN
  local budget = math.max(0.5, 0.98 - overhead_frac)

  local total = 0
  for i = 1, n do total = total + totlen[i] end
  if total == 0 then total = 1 end

  -- minw is a hard floor: the width the column's single longest unbreakable
  -- word needs. desired is what content volume would like to have. Below,
  -- if the desireds don't all fit, only the slack ABOVE each column's floor
  -- gets squeezed -- never the floor itself. A uniform scale-down here would
  -- shrink already-minimal columns below their word-fit width, and since
  -- LaTeX can't hyphenate a word it doesn't wrap it -- it silently overflows
  -- the column box into whatever sits to the right instead of erroring.
  local minw, desired = {}, {}
  for i = 1, n do
    local content_frac = totlen[i] / total
    local word_frac = (maxword[i] + 2) / FULL_WIDTH_CHARS
    minw[i] = math.max(0.04, math.min(0.60, word_frac))
    desired[i] = math.max(minw[i], math.min(0.60, content_frac))
  end

  local sum_desired = 0
  for i = 1, n do sum_desired = sum_desired + desired[i] end
  if sum_desired <= budget then
    return desired
  end

  local sum_min = 0
  for i = 1, n do sum_min = sum_min + minw[i] end
  if sum_min >= budget then
    -- Even every column's bare minimum doesn't fit the budget -- last
    -- resort: scale the floors themselves (rare; many long-word columns).
    local scale = budget / sum_min
    local widths = {}
    for i = 1, n do widths[i] = minw[i] * scale end
    return widths
  end

  local slack_total = sum_desired - sum_min
  local shrink_ratio = (sum_desired - budget) / slack_total
  local widths = {}
  for i = 1, n do
    widths[i] = desired[i] - (desired[i] - minw[i]) * shrink_ratio
  end
  return widths
end

-- Renders a table as a raw LaTeX longtable with explicit \\hline / "|" grid
-- lines, since pandoc's own booktabs-style output only ever draws a rule
-- above the header, below the header, and at the very end -- there is no
-- built-in way to ask pandoc for a line after every body row or for vertical
-- column rules. pandoc.write() isn't available in this pandoc's Lua API
-- (pandoc-types 1.20 / pandoc 2.9), so cell content is converted to LaTeX by
-- hand, covering the inline styles markdown tables actually use.
local function align_cmd(a)
  if a == "AlignRight" then return "\\\\raggedleft\\\\arraybackslash"
  elseif a == "AlignCenter" then return "\\\\centering\\\\arraybackslash"
  else return "\\\\raggedright\\\\arraybackslash" end
end

local function escape_latex(s)
  s = s:gsub("\\\\", "\\\\textbackslash{}")
  s = s:gsub("([%%$#&_{}])", "\\\\%1")
  s = s:gsub("~", "\\\\textasciitilde{}")
  s = s:gsub("%^", "\\\\textasciicircum{}")
  return s
end

local function inlines_to_latex(inlines)
  local parts = {}
  for _, il in ipairs(inlines) do
    local t = il.t
    if t == "Str" then
      table.insert(parts, escape_latex(il.text))
    elseif t == "Space" or t == "SoftBreak" then
      table.insert(parts, " ")
    elseif t == "LineBreak" then
      table.insert(parts, "\\\\\\\\ ")
    elseif t == "Emph" then
      table.insert(parts, "\\\\emph{" .. inlines_to_latex(il.content) .. "}")
    elseif t == "Strong" then
      table.insert(parts, "\\\\textbf{" .. inlines_to_latex(il.content) .. "}")
    elseif t == "Code" then
      table.insert(parts, "\\\\texttt{" .. escape_latex(il.text) .. "}")
    elseif t == "Math" then
      table.insert(parts, "$" .. il.text .. "$")
    elseif t == "Link" then
      table.insert(parts, "\\\\href{" .. il.target[1] .. "}{" .. inlines_to_latex(il.content) .. "}")
    elseif il.content then
      table.insert(parts, inlines_to_latex(il.content))
    else
      local ok, s = pcall(pandoc.utils.stringify, il)
      table.insert(parts, ok and escape_latex(s) or "")
    end
  end
  return table.concat(parts)
end

local function blocks_to_latex(blocks)
  local parts = {}
  for _, b in ipairs(blocks) do
    if b.t == "Para" or b.t == "Plain" then
      table.insert(parts, inlines_to_latex(b.content))
    else
      local ok, s = pcall(pandoc.utils.stringify, b)
      table.insert(parts, ok and escape_latex(s) or "")
    end
  end
  return table.concat(parts, " \\\\newline{} ")
end

local function cell_to_latex(blocks)
  local ok, latex = pcall(blocks_to_latex, blocks)
  if not ok or not latex then return "" end
  return latex
end

local function render_grid_table(n, aligns, widths, header_cells, body_rows, caption_inlines)
  local vbar = GRID_V and "|" or ""
  local hline = GRID_H and "\\\\hline" or ""

  local colspec_parts = {vbar}
  for i = 1, n do
    table.insert(colspec_parts,
      string.format(">{%s}p{%.4f\\\\linewidth}", align_cmd(aligns[i]), widths[i]))
    table.insert(colspec_parts, vbar)
  end

  local lines = {}
  table.insert(lines, "\\\\begin{longtable}{" .. table.concat(colspec_parts) .. "}")

  if caption_inlines and #caption_inlines > 0 then
    local cap = cell_to_latex({pandoc.Para(caption_inlines)})
    if cap ~= "" then
      table.insert(lines, "\\\\caption{" .. cap .. "}\\\\\\\\")
    end
  end

  if hline ~= "" then table.insert(lines, hline) end

  if header_cells and #header_cells > 0 then
    local hdr = {}
    for i, cell in ipairs(header_cells) do
      table.insert(hdr, "\\\\textbf{" .. cell_to_latex(cell) .. "}")
    end
    table.insert(lines, table.concat(hdr, " & ") .. " \\\\\\\\")
    if hline ~= "" then table.insert(lines, hline) end
    table.insert(lines, "\\\\endhead")
  end

  for _, row in ipairs(body_rows) do
    local cells = {}
    for i, cell in ipairs(row) do
      if i <= n then table.insert(cells, cell_to_latex(cell)) end
    end
    table.insert(lines, table.concat(cells, " & ") .. " \\\\\\\\")
    if hline ~= "" then table.insert(lines, hline) end
  end

  table.insert(lines, "\\\\end{longtable}")
  return pandoc.RawBlock("latex", table.concat(lines, "\\n"))
end

-- pandoc >= 2.10 (pandoc-types >= 1.22): Table has colspecs/head/bodies.
-- pandoc < 2.10 (pandoc-types < 1.22, e.g. 2.9.x): Table has widths/headers/rows,
-- and each cell is a plain list of Blocks rather than a Cell object.
function Table(t)
  if t.colspecs then
    local n = #t.colspecs
    if n == 0 then return t end

    local totlen, maxword = {}, {}
    for i = 1, n do totlen[i], maxword[i] = 4, 0 end

    for _, row in ipairs(t.head.rows) do
      for i, cell in ipairs(row.cells) do
        if i <= n then
          local tl, mw = col_stats(cell.content)
          if tl > totlen[i] then totlen[i] = tl end
          if mw > maxword[i] then maxword[i] = mw end
        end
      end
    end

    for _, body in ipairs(t.bodies) do
      for _, row in ipairs(body.body) do
        for i, cell in ipairs(row.cells) do
          if i <= n then
            local tl, mw = col_stats(cell.content)
            if tl > totlen[i] then totlen[i] = tl end
            if mw > maxword[i] then maxword[i] = mw end
          end
        end
      end
    end

    local widths = compute_widths(n, totlen, maxword)
    for i = 1, n do t.colspecs[i][2] = widths[i] end

    if not (GRID_H or GRID_V) then return t end

    local aligns = {}
    for i = 1, n do aligns[i] = tostring(t.colspecs[i][1]) end

    local header_cells = {}
    if t.head.rows[1] then
      for i, cell in ipairs(t.head.rows[1].cells) do
        if i <= n then header_cells[i] = cell.content end
      end
    end

    local body_rows = {}
    for _, body in ipairs(t.bodies) do
      for _, row in ipairs(body.body) do
        local cells = {}
        for i, cell in ipairs(row.cells) do
          if i <= n then cells[i] = cell.content end
        end
        table.insert(body_rows, cells)
      end
    end

    return render_grid_table(n, aligns, widths, header_cells, body_rows, nil)
  end

  -- Old-style Table (pandoc-types < 1.22)
  local n = #t.headers
  if n == 0 and t.rows[1] then n = #t.rows[1] end
  if n == 0 then return t end

  local totlen, maxword = {}, {}
  for i = 1, n do totlen[i], maxword[i] = 4, 0 end

  for i, cell in ipairs(t.headers) do
    if i <= n then
      local tl, mw = col_stats(cell)
      if tl > totlen[i] then totlen[i] = tl end
      if mw > maxword[i] then maxword[i] = mw end
    end
  end

  for _, row in ipairs(t.rows) do
    for i, cell in ipairs(row) do
      if i <= n then
        local tl, mw = col_stats(cell)
        if tl > totlen[i] then totlen[i] = tl end
        if mw > maxword[i] then maxword[i] = mw end
      end
    end
  end

  t.widths = compute_widths(n, totlen, maxword)

  if not (GRID_H or GRID_V) then return t end

  return render_grid_table(n, t.aligns, t.widths, t.headers, t.rows, t.caption)
end
""".replace("__FULL_WIDTH_CHARS__", str(_full_width_chars)) \
   .replace("__TEXT_WIDTH_IN__", str(_text_width_in)) \
   .replace("__TABCOLSEP_IN__", str(_tabcolsep_in)) \
   .replace("__GRID_H__", "true" if h_lines else "false") \
   .replace("__GRID_V__", "true" if v_lines else "false")

    cmd = [
        "pandoc", str(md_path),
        "--pdf-engine=xelatex",
        "--resource-path=.",
        f"-V", f"mainfont={font}",
        f"-V", "sansfont=DejaVu Sans",
        f"-V", f"monofont={mono_font}",
        f"-V", "monofontoptions=Scale=0.88",
        f"-V", f"geometry=margin={margin}",
        f"-V", f"fontsize={font_size}",
        f"-V", "colorlinks=true",
        f"-V", "linkcolor=NavyBlue",
        f"-V", "urlcolor=NavyBlue",
        f"-V", "toccolor=black",
        f"-V", "linestretch=1.15",
        "--standalone",
        "-f", "markdown+smart",
        "-o", str(out_path),
    ]
    if toc:
        cmd += ["--toc", f"--toc-depth={toc_depth}"]
    # \tabcolsep is trimmed for every table (not just grid ones) since it
    # trades directly against the column-width budget the lua filter above
    # computes -- the default 6pt costs a many-column table real inches of
    # page width it never gets to spend on content.
    _header_includes = f"\\setlength{{\\tabcolsep}}{{{_tabcolsep_pt:g}pt}}"
    if h_lines or v_lines:
        # Grid-line tables are emitted as raw `longtable` LaTeX by the lua
        # filter below, which bypasses pandoc's own table detection (the
        # $tables$ template variable), so the packages it needs must be
        # pulled in explicitly here.
        _header_includes += "\\usepackage{longtable}\\usepackage{array}"
    cmd += ["-V", f"header-includes={_header_includes}"]

    lua_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as lf:
            lf.write(_LUA_AUTO_TABLE_WIDTHS)
            lua_path = lf.name
        cmd += [f"--lua-filter={lua_path}"]

        result = subprocess.run(
            cmd,
            cwd=str(md_path.parent),   # resolve relative image paths correctly
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stderr.strip():
            click.echo(result.stderr.strip(), err=True)
        click.echo(f"Done: {out_path}")
    except FileNotFoundError:
        raise click.ClickException(
            "pandoc not found. Install with: sudo apt install pandoc texlive-xetex"
        )
    except subprocess.CalledProcessError as e:
        click.echo(e.stderr, err=True)
        raise click.ClickException("pandoc conversion failed (see errors above).")
    finally:
        import os
        if lua_path:
            try:
                os.unlink(lua_path)
            except Exception:
                pass

