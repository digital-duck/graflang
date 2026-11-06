"""A small Markdown to HTML converter for `graf docs` (headings with ids, paragraphs, lists, tables, code fences, quotes, links).

It covers what the documentation styles write; it is not a full CommonMark. No dependency. Heading ids are the GitHub anchors, so the
`[title](#anchor)` links of the document's Contents work in the page as they do on GitHub. Everything is escaped before it is marked up.
"""
import html
import re

CSS = """body{font:16px/1.6 system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#1f2933}
h1,h2,h3{line-height:1.25}h2{border-bottom:1px solid #d8dee4;padding-bottom:.2rem;margin-top:2rem}
code{background:#f1f3f5;padding:.1em .3em;border-radius:3px;font-size:.92em}
pre.mermaid{background:none;text-align:center}pre{background:#f6f8fa;padding:.8rem 1rem;overflow:auto;border-radius:6px}pre code{background:none;padding:0}
table{border-collapse:collapse;margin:1rem 0}th,td{border:1px solid #d0d7de;padding:.35rem .6rem;text-align:left}th{background:#f6f8fa}
blockquote{margin:1rem 0;padding:.1rem 1rem;border-left:4px solid #d0d7de;color:#57606a}a{color:#0969da}
@media print{body{max-width:none;margin:0}a{color:inherit}}"""


def slug(title: str) -> str:
    t = re.sub(r"[`*_]|<[^>]+>", "", title).strip().lower()
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", t))


def inline(text: str) -> str:
    codes = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\0{len(codes) - 1}\0"

    t = re.sub(r"`([^`]+)`", keep, text)
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>'
               if not m.group(2).lower().startswith("javascript:") else m.group(1), t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"\0(\d+)\0", lambda m: codes[int(m.group(1))], t)


def cells(row: str):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def convert(md: str, title: str = "") -> str:
    lines, out, seen, k, diagrams = md.split("\n"), [], {}, 0, 0
    page_title = title
    while k < len(lines):
        ln = lines[k]
        if ln.startswith("```"):
            lang, buf, k = ln[3:].strip(), [], k + 1
            while k < len(lines) and not lines[k].startswith("```"):
                buf.append(lines[k])
                k += 1
            cls = f' class="language-{html.escape(lang, quote=True)}"' if lang else ""
            if lang == "mermaid":
                diagrams += 1
                out.append(f'<pre class="mermaid">{html.escape(chr(10).join(buf))}</pre>')
                k += 1
                continue
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
            k += 1
        elif m := re.match(r"^(#{1,6}) (.+?)\s*#*$", ln):
            n, text = len(m.group(1)), m.group(2)
            base = slug(text)
            c = seen.get(base, 0)
            seen[base] = c + 1
            if n == 1 and not page_title:
                page_title = re.sub(r"[`*]", "", text)
            out.append(f'<h{n} id="{base if c == 0 else f"{base}-{c}"}">{inline(text)}</h{n}>')
            k += 1
        elif re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", ln):
            out.append("<hr>")
            k += 1
        elif ln.startswith("|") and k + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[k + 1]):
            head, rows, k = cells(ln), [], k + 2
            while k < len(lines) and lines[k].startswith("|"):
                rows.append(cells(lines[k]))
                k += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>")
        elif ln.startswith(">"):
            buf = []
            while k < len(lines) and lines[k].startswith(">"):
                buf.append(lines[k].lstrip("> ").rstrip())
                k += 1
            out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>")
        elif re.match(r"^\s*([-*]|\d+\.) ", ln):
            out_list, k = list_block(lines, k)
            out.append(out_list)
        elif not ln.strip():
            k += 1
        else:
            buf = []
            while k < len(lines) and lines[k].strip() and not re.match(r"^(```|#{1,6} |\||>|\s*([-*]|\d+\.) )", lines[k]):
                buf.append(lines[k].strip())
                k += 1
            out.append(f"<p>{inline(' '.join(buf))}</p>")
    boot = ('<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";'
            'mermaid.initialize({startOnLoad:true,securityLevel:"strict"});</script>\n') if diagrams else ""     # offline, the diagram text stays readable
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(page_title or 'document')}</title>\n<style>{CSS}</style>\n</head>\n<body>\n" + "\n".join(out) + "\n" + boot + "</body>\n</html>\n")


def list_block(lines, k):
    """A (possibly nested) bullet or numbered list starting at line k; nesting by indentation. Returns (html, next line)."""
    def item(ln):
        m = re.match(r"^(\s*)([-*]|\d+\.) (.*)$", ln)
        return (len(m.group(1)), m.group(2)[0].isdigit(), m.group(3)) if m else None

    def build(k, indent):
        first = item(lines[k])
        tag = "ol" if first[1] else "ul"
        parts = [f"<{tag}>"]
        while k < len(lines):
            it = item(lines[k])
            if it is None or it[0] < indent:
                break
            if it[0] > indent:
                sub, k = build(k, it[0])
                parts[-1] = parts[-1][:-5] + sub + "</li>"
                continue
            text, k = it[2], k + 1
            while k < len(lines) and lines[k].strip() and item(lines[k]) is None and re.match(r"^\s+\S", lines[k]):
                text += " " + lines[k].strip()
                k += 1
            parts.append(f"<li>{inline(text)}</li>")
        parts.append(f"</{tag}>")
        return "".join(parts), k

    return build(k, item(lines[k])[0])
