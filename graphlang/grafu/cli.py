"""`graf util`: conversion and document helpers (ported from `spl3 util`).

Here (no SPL runtime needed): the architecture-graph tools (arch2mmd, mmd2arch, arch-drift, arch-gate), clean-port and mmd2img. The document
conversions (html2pdf, md2html, md2pdf) are thin wrappers over dd-format (`pip install "graflang[format]"`).
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


# ---- html2pdf (dd-format's html_to_pdf) -------------------------------------------------------------------------------------------

_NEED_DD_FORMAT = "this command is dd-format's ({e}): pip install \"graflang[format]\" (or: pip install dd-format)"


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

    try:
        from dd_format.html_pdf import HtmlToPdfError, count_pages, html_to_pdf
    except ImportError as e:
        raise click.ClickException(_NEED_DD_FORMAT.format(e=e))
    try:
        out = html_to_pdf(Path(html_file), Path(output) if output else None, browser=browser, timeout=timeout)
    except HtmlToPdfError as exc:
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
            if fmt == "pdf":
                args.append("--pdfFit")  # one page sized to the diagram, not paginated A4
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
    from pathlib import Path

    try:
        from dd_format.pandoc_pdf import PandocError, markdown_to_pdf_pandoc
    except ImportError as e:
        raise click.ClickException(_NEED_DD_FORMAT.format(e=e))
    try:
        markdown_to_pdf_pandoc(Path(md_file), output, font=font, mono_font=mono_font, font_size=font_size, margin=margin, toc=toc,
                                     toc_depth=toc_depth, h_lines=h_lines, v_lines=v_lines, log=lambda m: click.echo(m, err=True))
    except PandocError as e:
        raise click.ClickException(str(e))



# ---- md2html (dd-format's markdown_to_html) ---------------------------------------------------------------------------------------------

@util.command("md2html", short_help="Convert a Markdown file to a standalone .html page (Mermaid diagrams drawn in the browser).")
@click.argument("md_file", metavar="MD_FILE")
@click.option("-o", "--output", default=None, metavar="HTML", help="Output file (default: next to the input, same name, .html).")
@click.option("--title", default="", metavar="TEXT", help="Page title (default: the first # heading).")
@click.option("--max-width", default="64rem", show_default=True, metavar="CSS", help="Page text width, any CSS length (e.g. 52rem, 1200px, none).")
def cmd_md2html(md_file, output, title, max_width):
    """Convert a Markdown file to one self-contained .html page (no LLM, no pandoc).

    Handles headings (GitHub anchors), paragraphs, lists, tables, code fences, quotes and links. A ```mermaid fence becomes a diagram,
    drawn in the browser by Mermaid 11 from a CDN (and its ELK loader when the diagram says `layout: elk`), so the page needs network
    access to show diagrams; offline the diagram source stays readable.

    \b
    Examples:
      graf util md2html readme-techstack.md
      graf util md2html notes.md -o out/notes.html --title "Notes" --max-width 80rem
    """
    from pathlib import Path

    try:
        from dd_format.html_writer import markdown_to_html
    except ImportError as e:
        raise click.ClickException(_NEED_DD_FORMAT.format(e=e))
    src = Path(md_file)
    if not src.is_file():
        raise click.ClickException(f"{md_file} not found")
    out = Path(output) if output else src.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    markdown_to_html(src.read_text(encoding="utf-8"), str(out), title=title, theme="light", max_width=max_width)
    click.echo(f"HTML: {out}")



# ---- arch2mmd (logic in grafu/arch2mmd.py) -------------------------------------------------------------------------------------------

@util.command("arch2mmd", short_help="Convert an architecture graph (.arch.yaml) to a Mermaid .mmd flowchart, after checking its rules.")
@click.argument("arch_file", metavar="ARCH_FILE")
@click.option("-o", "--output", default=None, metavar="MMD", help="Output file (default: next to the input, NAME.arch.yaml -> NAME.mmd).")
@click.option("--check", is_flag=True, help="Only validate the graph (rules, unknown nodes, cycles); write nothing.")
@click.option("--strict", is_flag=True, help="Treat warnings (e.g. a node with no edges) as errors.")
@click.option("--verify", is_flag=True, help="Write nothing: draw the graph, read the drawing back (arch -> mmd -> arch) and compare. Exit 1 if anything is lost.")
def cmd_arch2mmd(arch_file, output, check, strict, verify):
    """Draw an architecture graph, graph-first: the `.arch.yaml` is the source of truth and the picture is generated from it.

    The file lists layers (each with a rank), groups, nodes and edges (`requires`, `optional`, `network`), plus the rules it must
    keep: edges never point up the layers, and `requires` edges have no cycle. The graph is checked before anything is drawn, so a
    picture never shows an architecture that breaks its own rules. Exit status is 1 if the check fails.

    \b
    Examples:
      graf util arch2mmd digital-duck.arch.yaml                 # -> digital-duck.mmd
      graf util arch2mmd digital-duck.arch.yaml --check         # validate only
      graf util arch2mmd digital-duck.arch.yaml -o out/stack.mmd && graf util mmd2img out/stack.mmd -f pdf
    """
    from .arch2mmd import ArchError, convert, load, validate

    try:
        if verify:
            from .mmd2arch import roundtrip_arch

            diffs = roundtrip_arch(load(arch_file))
            if diffs:
                click.echo(f"LOSSY: {len(diffs)} difference(s) after arch -> mmd -> arch:", err=True)
                for d in diffs[:20]:
                    click.echo(f"  {d}", err=True)
                raise SystemExit(1)
            click.echo(f"OK: {arch_file} -> mmd -> arch is identical")
            return
        if check:
            errors, warnings = validate(load(arch_file))
            for w in warnings:
                click.echo(f"warning: {w}", err=True)
            if errors or (strict and warnings):
                raise ArchError("\n".join("  " + m for m in errors + (warnings if strict else [])))
            click.echo(f"OK: {arch_file}")
            return
        dest, warnings = convert(arch_file, output, strict=strict)
    except FileNotFoundError:
        raise click.ClickException(f"{arch_file} not found")
    except ArchError as exc:
        raise click.ClickException(f"{arch_file}:\n{exc}")
    for w in warnings:
        click.echo(f"warning: {w}", err=True)
    click.echo(f"MMD: {dest}")


# ---- mmd2arch (logic in grafu/mmd2arch.py) -------------------------------------------------------------------------------------------

@util.command("mmd2arch", short_help="Convert a Mermaid .mmd flowchart back to an architecture graph (.arch.yaml); --verify proves the round trip is lossless.")
@click.argument("mmd_file", metavar="MMD_FILE")
@click.option("-o", "--output", default=None, metavar="ARCH", help="Output file (default: next to the input, NAME.mmd -> NAME.arch.yaml).")
@click.option("--verify", is_flag=True, help="Write nothing: read the picture into an architecture, draw that again, and compare the two pictures. Exit 1 if they differ.")
def cmd_mmd2arch(mmd_file, output, verify):
    """Read a Mermaid flowchart as an architecture graph: the inverse of `graf util arch2mmd`.

    Layers (`N · Title` subgraphs), groups, nodes (name, commands, summary lines), edges (solid = requires, dashed = optional), classes and
    styles come from the picture. What a picture cannot show (package names, rules, network edges) comes from the `%% arch-meta:` line that
    `arch2mmd` writes; a hand-written `.mmd` has none and gets defaults, which the command reports.

    The round trip is how fidelity is shown: `--verify` reads the picture, draws it again and diffs the two. For an architecture file the
    other direction is `graf util arch2mmd FILE --verify` (arch -> mmd -> arch).

    \b
    Examples:
      graf util mmd2arch dd-techstack-chart.mmd                  # -> dd-techstack-chart.arch.yaml
      graf util mmd2arch dd-techstack-chart.mmd --verify         # prove nothing in the picture is lost
    """
    from pathlib import Path

    from .mmd2arch import convert, roundtrip_mmd

    path = Path(mmd_file)
    if not path.is_file():
        raise click.ClickException(f"{mmd_file} not found")
    if verify:
        diffs = roundtrip_mmd(path.read_text(encoding="utf-8"))
        if diffs:
            click.echo(f"LOSSY: {len(diffs)} difference(s) between {mmd_file} and its re-drawing:", err=True)
            for d in diffs[:20]:
                click.echo(f"  {d}", err=True)
            raise SystemExit(1)
        click.echo(f"OK: {mmd_file} -> arch -> mmd draws the same picture")
        return
    dest, notes = convert(path, output)
    for note in notes:
        click.echo(f"note: {note}", err=True)
    click.echo(f"ARCH: {dest}")


# ---- arch-drift (logic in grafu/arch_drift.py) ---------------------------------------------------------------------------------------

@util.command("arch-drift", short_help="Compare an architecture graph's edges with what each repo's pyproject.toml really depends on.")
@click.argument("arch_file", metavar="ARCH_FILE")
@click.option("--root", default=".", show_default=True, metavar="DIR", help="Folder that holds the repos the nodes name with `repo:`.")
@click.option("--strict", is_flag=True, help="Treat warnings as errors too.")
def cmd_arch_drift(arch_file, root, strict):
    """Check that the code still matches the architecture: the "validate" step of arch-design -> prototype -> validate.

    For every node that names a `pkg` and a `repo`, the repo's `pyproject.toml` dependencies (and extras) are compared with the graph's
    `requires` / `optional` edges. A dependency the graph lacks, or an edge the code does not use, is an error; a `requires` edge the code has
    only as an extra (or the reverse) is a warning. Exit status is 1 on any error.

    \b
    Example:
      graf util arch-drift digital-duck.arch.yaml --root ~/projects/digital-duck
    """
    from .arch2mmd import load
    from .arch_drift import drift

    try:
        arch = load(arch_file)
    except FileNotFoundError:
        raise click.ClickException(f"{arch_file} not found")
    findings = drift(arch, root)
    for f in findings:
        click.echo(str(f), err=not f.is_error)
    errors = [f for f in findings if f.is_error or strict]
    click.echo(f"{'DRIFT' if errors else 'OK'}: {len(findings)} finding(s)" + (f", {len(errors)} counted as errors" if findings else ""))
    if errors:
        raise SystemExit(1)


# ---- arch-gate (logic in grafu/arch_gate.py) -----------------------------------------------------------------------------------------

@util.command("arch-gate", short_help="Fail when a component claims a lifecycle status (prototype, validated, product) its contract and code have not earned.")
@click.argument("arch_file", metavar="ARCH_FILE")
@click.option("--root", default=".", show_default=True, metavar="DIR", help="Folder that holds the repos the nodes name with `repo:`.")
@click.option("--all", "show_all", is_flag=True, help="Also list the components that have no `status` (they are never gated).")
@click.option("--run-cited", is_flag=True, help="Also RUN the tests the guarantees cite (in each node's repo) and refuse `product` where one failed, was skipped or was not found.")
@click.option("--python", "python", default=None, metavar="EXE", help="With --run-cited: the interpreter that runs pytest (default: the one running graf). It needs each repo's test dependencies.")
@click.option("--timeout", default=300, show_default=True, help="With --run-cited: seconds allowed per test file.")
@click.option("--node", "only", multiple=True, metavar="ID", help="With --run-cited: run only this node's cited tests (repeatable).")
def cmd_arch_gate(arch_file, root, show_all, run_cited, python, timeout, only):
    """The promotion gate of the design cycle: arch-design -> prototype -> validate -> product.

    Each node may declare `status: planned | prototype | validated | product` and a `contract` (`tests`, `files`, `guarantees`). The gate works
    out the status each node has really earned and exits 1 when a node claims more:

    \b
      prototype   the repo exists
      validated   + contract tests/files exist, and `arch-drift` finds no error for the node
      product     + the contract states guarantees (each cited `path.py::test_name` must exist), and every `requires` target has earned `product`

    A guarantee may cite the test that proves it. `--run-cited` runs those tests for real, so a cited test that fails, is skipped (a missing optional
    package, a server that is down) or is not collected also blocks `product`: a skipped test proves nothing. Exit status is 1 if any rated node
    claims more than it earned, or if any cited test of a rated node did not pass.

    \b
    Examples:
      graf util arch-gate digital-duck.arch.yaml --root ~/projects/digital-duck
      graf util arch-gate digital-duck.arch.yaml --root ~/projects/digital-duck --run-cited
      graf util arch-gate digital-duck.arch.yaml --root ~/projects/digital-duck --run-cited --node dd-config --python ~/anaconda3/envs/graf/bin/python
    """
    from .arch2mmd import ArchError, load, validate
    from .arch_gate import gate, run_cited as run_cited_tests

    try:
        arch = load(arch_file)
    except FileNotFoundError:
        raise click.ClickException(f"{arch_file} not found")
    errors, _ = validate(arch)
    if errors:
        raise click.ClickException(f"{arch_file}:\n" + "\n".join("  " + e for e in errors))
    evidence = None
    if run_cited:
        click.echo("running the cited tests ...", err=True)
        evidence = run_cited_tests(arch, root, python=python, timeout=timeout, only=list(only) or None)
    results = gate(arch, root, evidence)
    bad = [r for r in results if not r.ok]
    for r in results:
        if r.claimed is None and not show_all:
            continue
        mark = "-" if r.claimed is None else ("ok " if r.ok else "FAIL")
        claim = r.claimed or "unrated"
        click.echo(f"{mark:5}{r.node:14} claims {claim:10} earned {r.earned}", err=not r.ok)
        if (not r.ok or r.claimed is None) and r.blockers:
            for b in r.blockers[:4]:
                click.echo(f"        next level blocked: {b}", err=not r.ok)
    rated = [r for r in results if r.claimed is not None]
    broken = []
    if evidence is not None:
        claimed = {r.node for r in rated}
        for nid, items in evidence.items():
            total = len(items)
            problems = [e for e in items if not e.ok]
            if nid in claimed or problems:
                click.echo(f"      evidence {nid}: {total - len(problems)}/{total} cited tests passed", err=bool(problems))
            for e in problems:
                click.echo(f"        {e}", err=True)
            if nid in claimed:
                broken += problems
    click.echo(f"{'GATE FAILED' if bad or broken else 'GATE OK'}: {len(rated) - len(bad)}/{len(rated)} rated component(s) hold their status; {len(results) - len(rated)} unrated"
               + (f"; {sum(len(v) for v in evidence.values())} cited tests run, {len(broken)} did not pass" if evidence is not None else ""))
    if bad or broken:
        raise SystemExit(1)