"""html2pdf: turn an .html slide deck (or any page) into a .pdf with headless Chromium/Chrome.

The page's own print stylesheet decides the layout (`@page` size, one `.slide` per page, backgrounds kept), so the
result matches the deck's browser "Print > Save as PDF" with Background graphics on.  No LLM, no network.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome")


class Html2PdfError(RuntimeError):
    pass


def find_browser(browser: Optional[str] = None) -> str:
    """The browser to use: `browser` (a name on PATH or a path), else $CHROME, else the first Chromium/Chrome found."""
    wanted = browser or os.environ.get("CHROME")
    if wanted:
        found = shutil.which(wanted)
        if not found:
            raise Html2PdfError(f"browser not found: {wanted}")
        return found
    for name in BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    raise Html2PdfError("no Chromium or Chrome on PATH; install one, or pass --browser / set CHROME")


def _command(browser: str, pdf: Path, html: Path) -> List[str]:
    return [browser, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
            f"--print-to-pdf={pdf}", html.resolve().as_uri()]


def _render(browser: str, html: Path, work: Path, timeout: int) -> Optional[Path]:
    pdf = work / "deck.pdf"
    try:
        subprocess.run(_command(browser, pdf, html), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return pdf if pdf.is_file() and pdf.stat().st_size > 0 else None


def html_to_pdf(html: Path, out: Optional[Path] = None, browser: Optional[str] = None, timeout: int = 120) -> Path:
    """Write `html` as a PDF and return its path (default: next to the html, same name, `.pdf`)."""
    html = Path(html)
    if not html.is_file():
        raise Html2PdfError(f"no such file: {html}")
    out = Path(out) if out else html.with_suffix(".pdf")
    exe = find_browser(browser)
    # A snap-packaged browser can write only to visible folders under $HOME, not to /tmp: try the system temp
    # folder first, then a visible one in the home folder.
    attempts = [lambda: tempfile.TemporaryDirectory(), lambda: tempfile.TemporaryDirectory(prefix="html2pdf-", dir=Path.home())]
    pdf_bytes: Optional[bytes] = None
    for make in attempts:
        with make() as tmp:
            pdf = _render(exe, html, Path(tmp), timeout)
            if pdf:
                pdf_bytes = pdf.read_bytes()
                break
    if pdf_bytes is None:
        raise Html2PdfError(f"{Path(exe).name} produced no PDF for {html}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf_bytes)
    return out


def count_pages(pdf: Path) -> int:
    """Page count by scanning for page objects (good enough to report; 0 if the file is not a plain PDF)."""
    import re
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", Path(pdf).read_bytes()))
