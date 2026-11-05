"""Turns the writer's text into the finished document and checks it.

stdin   one JSON object: {body, gathered (the gather.py JSON, as text), source}
stdout  one line of JSON: {document, ok, errors, warnings, sections}
exit    0 whenever it could judge (`ok` says whether the document is good); 1 only when stdin is unusable.

What it does
  markdown   strips a fence around the whole answer; checks there is a `# ` title, at least `min_sections` `## ` sections and balanced code fences.
  html       takes the `<section class="slide">` elements of the answer, removes anything active (script, style, link, iframe, object, on*= handlers,
             javascript: urls, external src), puts an outline slide after the cover and wraps them in the style's template; checks there are
             at least `min_sections` slides, each closed, each with a title (the cover an h1), and that the page is a whole document.
  both       lists every `code` token that looks like a path of the source and does not exist there (a warning: the writer may have invented it).
`ok` is false only for structure errors; unverified paths are warnings. Nothing here calls a model.
"""
import html as htmllib
import json
import re
import sys
from pathlib import Path

OUTLINE = ('<section class="slide" id="outline">\n  <h2>Outline</h2>\n  <ol class="toc" id="toc"></ol>\n'
           '  <aside class="notes">The outline lists every slide title; click a line to jump.</aside>\n</section>')
EXT = r"\.(py|md|yaml|yml|json|toml|js|ts|rs|go|sh|html|txt|cfg|ini)"
PATHISH = re.compile(rf"^[\w.\-]+(/[\w.\-]+)*{EXT}$|^[\w.\-]+(/[\w.\-]+)*/$")      # a file with a known extension, or a folder written with a trailing slash


def parse(stdout: str):
    return json.loads(stdout)


def unfence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", text, re.S)
    return m.group(1) if m else text


def sanitize(markup: str):
    """Remove what makes a page active; returns (clean markup, list of what was removed)."""
    removed = []

    def drop(pattern, label, flags=re.S | re.I):
        nonlocal markup
        markup, n = re.subn(pattern, "", markup, flags=flags)
        if n:
            removed.append(f"{n} {label}")

    drop(r"<script\b.*?</script\s*>", "script element(s)")
    drop(r"<style\b.*?</style\s*>", "style element(s)")
    drop(r"<(iframe|object|embed|link|meta|base|form)\b[^>]*>(.*?</\1\s*>)?", "embedded or form element(s)")
    markup, n = re.subn(r"""\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", "", markup, flags=re.I)
    if n:
        removed.append(f"{n} event handler(s)")
    markup, n = re.subn(r"""(href|src)\s*=\s*(["'])\s*javascript:[^"']*\2""", r"\1=\2#\2", markup, flags=re.I)
    if n:
        removed.append(f"{n} javascript: url(s)")
    markup, n = re.subn(r"""<(img|source|video|audio)\b[^>]*\bsrc\s*=\s*["']\s*(https?:)?//[^>]*>""", "", markup, flags=re.I)
    if n:
        removed.append(f"{n} external image or media element(s)")
    return markup, removed


def slides_of(body: str):
    return re.findall(r"<section\b[^>]*class=\"[^\"]*\bslide\b[^\"]*\"[^>]*>.*?</section\s*>", body, re.S | re.I)


def paths_not_found(text: str, root: Path):
    index = None
    bad = []
    for token in sorted(set(re.findall(r"<code>(.*?)</code>|`([^`\n]+)`", text))):
        t = (token[0] or token[1]).strip()
        t = htmllib.unescape(re.sub(r"<[^>]+>", "", t))
        if not PATHISH.match(t) or t.startswith(("http", "~", "/", "$", ".")) and not t.startswith("./"):
            continue
        t = t[2:] if t.startswith("./") else t
        if (root / t.rstrip("/")).exists():
            continue
        if index is None:
            index = {p.name for p in root.rglob("*") if ".git" not in p.parts}
        if "/" not in t and t in index:
            continue
        bad.append(t)
    return bad


def main() -> int:
    try:
        job = json.load(sys.stdin)
        g = json.loads(job["gathered"]) if isinstance(job["gathered"], str) else job["gathered"]
    except (ValueError, KeyError) as e:
        print(f"assemble: bad input: {e}", file=sys.stderr)
        return 1
    body = unfence(str(job.get("body", "")))
    fmt, need = g.get("format", "markdown"), int(g.get("min_sections", 3))
    errors, warnings = [], []
    if not body.strip():
        errors.append("the writer returned nothing")

    if fmt == "html" and g.get("template"):
        clean, removed = sanitize(body)
        slides = slides_of(clean)
        if removed:
            warnings.append("removed from the slides: " + ", ".join(removed))
        if len(slides) < need:
            errors.append(f"found {len(slides)} slide(s) (<section class=\"slide\">), need at least {need}")
        for k, s in enumerate(slides, 1):
            if not re.search(r"<h[12]\b", s):
                errors.append(f"slide {k} has no title (h1 for the cover, h2 for the others)")
        if slides and not re.search(r"<h1\b", slides[0]):
            errors.append("the first slide is not a cover (it has no h1)")
        titles = [re.sub(r"<[^>]+>", "", t).strip() for s in slides for t in re.findall(r"<h2\b[^>]*>(.*?)</h2>", s, re.S)]
        page = Path(g["template"]).read_text(encoding="utf-8")
        title = htmllib.escape(g.get("name", "document"), quote=True)
        deck = "\n\n".join(slides[:1] + [OUTLINE] + slides[1:]) if slides else ""
        document, sections = page.replace("{{TITLE}}", title).replace("{{SLIDES}}", deck), len(slides)
        if "{{" in document.replace("{{in_", ""):
            warnings.append("the page still has an unfilled {{...}} marker")
    elif fmt == "html":
        document, sections = body, len(re.findall(r"<h[12]\b", body))
        if not re.search(r"<html\b", body, re.I):
            errors.append("a custom html document must be a whole page (<html>...)")
        if sections < need:
            errors.append(f"found {sections} heading(s), need at least {need}")
    else:
        document, sections = body, len(re.findall(r"^## ", body, re.M))
        if not re.match(r"^# \S", body):
            errors.append("the document must start with a `# ` title")
        if sections < need:
            errors.append(f"found {sections} section(s) (`## `), need at least {need}")
        if len(re.findall(r"^```", body, re.M)) % 2:
            errors.append("a code fence is not closed")

    missing = paths_not_found(body, Path(job.get("source") or g.get("root", ".")))
    if missing:
        warnings.append("paths in code that are not in the source (check them): " + ", ".join(missing[:25]) + (" ..." if len(missing) > 25 else ""))
    print(json.dumps({"document": document, "ok": not errors, "errors": errors, "warnings": warnings, "sections": sections}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
