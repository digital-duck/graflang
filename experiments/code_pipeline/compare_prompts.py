"""Check that the graflang arm sends the same prompts as the spl arm, for the same task.

    python compare_prompts.py <spl run folder>/prompts <graflang run folder>/prompts

graflang writes one folder per procedure call (001-00_analyze_spec, 002-01_generate_code, ...), in call order.

What is compared, and what cannot be:
1. The kinds of prompt, in order (analyze, generate, review, improve, test, document, extract, one set per cycle).
2. The spec-only prompts (the spec analyst and the first coder call) must match exactly: nothing in them depends on a model's output.
3. Every other prompt must keep the fixed text of its template (the .spl file in graflang's cookbook): the words between the
   placeholders must appear in order. The variable parts (the code, the feedback) come from earlier model output, so two runs
   cannot be expected to match there; the template is what the arms share.
4. The templates of the two copies (graflang's cookbook and SPL.py's cookbook/050) must be identical.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arms  # noqa: E402
import lg_pipeline  # noqa: E402  (load_prompts reads the templates from graflang's cookbook)

SPL_COPY = arms.SPL_DIR


def body(path: Path) -> str:
    """The prompt text, without the header SPL writes (title, model, budget and a line of dashes)."""
    text = path.read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1].strip() if "\n---\n" in text else text.strip()


def kind(path: Path) -> str:
    return re.sub(r"_\d+$", "", path.stem)


def fixed_pieces(template: str) -> list[str]:
    return [p.strip() for p in re.split(r"\{\w+\}", template) if p.strip()]


def follows_template(text: str, template: str) -> bool:
    at = 0
    for piece in fixed_pieces(template):
        at = text.find(piece, at)
        if at < 0:
            return False
        at += len(piece)
    return True


def main(spl_dir: Path, graf_dir: Path) -> int:
    templates = lg_pipeline.load_prompts()
    ok = True

    print("1. Templates: graflang's cookbook against SPL.py's copy")
    spl_templates = {}
    for path in sorted(SPL_COPY.glob("0[0-7]_*.spl")):
        for name, _, text in re.findall(r"CREATE FUNCTION (\w+)\(([^)]*)\)\s*RETURN TEXT\s*AS \$\$\n(.*?)\n\$\$;",
                                        path.read_text(encoding="utf-8"), re.S):
            spl_templates[name] = text
    for name in sorted(templates):
        same = spl_templates.get(name) == templates[name][1]
        ok &= same
        print(f"   {name:14} {'identical' if same else 'DIFFERENT'}")

    spl_files = sorted(spl_dir.glob("*.md"), key=lambda p: int(p.stem.split("_")[-1]))
    graf_files = sorted(graf_dir.glob("*/*.md"), key=lambda p: (p.parent.name, p.name))
    spl_kinds = [kind(p) for p in spl_files]
    graf_kinds = [kind(p) for p in graf_files]
    print(f"\n2. Order of prompts: spl {len(spl_files)}, graflang {len(graf_files)}")
    same_order = spl_kinds == graf_kinds
    ok &= same_order
    print(f"   {'same kinds in the same order' if same_order else 'DIFFERENT'}")
    if not same_order:
        print(f"   spl:      {spl_kinds}\n   graflang: {graf_kinds}")

    print("\n3. Spec-only prompts match exactly")
    for name in ("spec_analyst", "coder"):
        s_first = next((p for p in spl_files if kind(p) == name), None)
        g_first = next((p for p in graf_files if kind(p) == name), None)
        if s_first is None or g_first is None:
            ok = False
            print(f"   {name:14} missing from one arm")
            continue
        same = body(s_first) == body(g_first)
        ok &= same
        print(f"   {name:14} {'identical' if same else 'DIFFERENT'} (first call of each arm)")

    print("\n4. Every prompt keeps its template's fixed text (in order)")
    for label, files in (("spl", spl_files), ("graflang", graf_files)):
        bad = [p.name for p in files if kind(p) in templates and not follows_template(body(p), templates[kind(p)][1])]
        ok &= not bad
        print(f"   {label:9} {len(files) - len(bad)}/{len(files)} follow their template" + (f"; not: {bad}" if bad else ""))

    print("\nRESULT:", "the two arms send the same prompts, as far as they can be compared" if ok else "DIFFERENCES FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
