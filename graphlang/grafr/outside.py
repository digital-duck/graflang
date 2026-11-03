"""`QUERY`, `EMIT` and `OBSERVE`: the three nodes that touch the world outside the graph.

    QUERY    read something in: a file (text, JSON, YAML or lines) in the graph's folder (or a folder it lists)
    EMIT     write something out: a file, the terminal, a webhook, or an e-mail to fixed recipients
             (a file path comes from `config.file`, or from an `in_file` port when the caller decides where)
    OBSERVE  record what passed by (to the log, and to the run's output folder) without ever stopping the run

`QUERY` and `EMIT` are risky: `graf validate` accepts them only behind a GUARD's `allow` port. The keys that decide where they
read, write or send (`file`, `channel`, `recipients`, `sender`, `smtp_host`, `smtp_port`, `allow_dirs`, plus `url` and
`allow_hosts`) are in CODE_KEYS, so a MUTATE delta can never add or change them. A path is kept inside the graph's folder (or a
folder listed in `allow_dirs`); a `..` or a link out of it is refused. Secrets (the SMTP password) are never in the graph: they
are read from the environment (`GRAF_SMTP_USER`, `GRAF_SMTP_PASSWORD`).

    - id: read_notes                  - id: tell_me
      type: QUERY                       type: EMIT
      config: {file: notes.md}          config: {channel: email, recipients: [me@example.com], sender: graf@example.com,
      ports: [trigger, complete,                  smtp_host: smtp.example.com, subject: "Run finished"}
              out_text]                 ports: [trigger, complete, in_content, out_receipt]

In a dry run (the `mock` adapter) an EMIT does nothing but report what it would have done, so trying a graph never writes a
file or sends a message. Pass `effects=True` to the runtime to make it real.
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import yaml

from ..logging_config import WARNING, get_logger, log_event

_log = get_logger("grafr.outside")

QUERY_FORMATS = ("text", "json", "yaml", "lines")
EMIT_CHANNELS = ("file", "stdout", "webhook", "email")
MAX_BYTES = 1_000_000
OBSERVE_PREVIEW = 400


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):               # a redirect could leave the allowlist
        return None


class OutsideError(RuntimeError):
    """A QUERY or EMIT failed (a refused path, a missing file, a failed send)."""


def _out_port(node: Dict, skip: Tuple[str, ...] = ("out_error",)) -> str | None:
    return next((p for p in node["ports"] if p.startswith("out_") and p not in skip), None)


def _confined(path: str, base_dir: Path, allow_dirs: List[str] | None = None) -> Path:
    """`path` resolved under the graph's folder (or a folder in `allow_dirs`); anything that resolves outside is refused."""
    roots = [Path(base_dir).resolve()] + [Path(d).expanduser().resolve() for d in (allow_dirs or [])]
    target = (roots[0] / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()   # resolve() follows links
    if not any(target == r or r in target.parents for r in roots):
        raise OutsideError(f"{path!r} is outside the graph's folder; list its folder in allow_dirs to allow it")
    return target


# ---- QUERY ---------------------------------------------------------------------------------------------------
def run_query(node: Dict, in_data: Dict[str, Any], base_dir: Path) -> Dict:
    cfg = node.get("config", {})
    name = in_data.get("in_file") or cfg.get("file")
    if not name:
        raise OutsideError(f"QUERY {node['id']!r}: no file (config.file, or an in_file port)")
    path = _confined(str(name), base_dir, cfg.get("allow_dirs"))
    limit = int(cfg.get("max_bytes", MAX_BYTES))
    try:
        if path.stat().st_size > limit:
            raise OutsideError(f"QUERY {node['id']!r}: {path.name} is larger than max_bytes ({limit})")
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if "default" in cfg:
            value: Any = cfg["default"]
            log_event(_log, "query.default", node=node["id"], file=str(name))
            port = _out_port(node)
            return {port: value} if port else {}
        raise OutsideError(f"QUERY {node['id']!r}: no such file {name!r} (give a `default` to continue without it)") from None
    except (OSError, UnicodeDecodeError) as e:
        raise OutsideError(f"QUERY {node['id']!r}: cannot read {name!r}: {e}") from None
    tail = cfg.get("tail")
    if tail:                                                     # a sliding window: only the last N lines of the file
        text = "\n".join(text.splitlines()[-int(tail):]) + ("\n" if text.endswith("\n") else "")
    fmt = cfg.get("format", "text")
    try:
        value = {"text": lambda: text, "json": lambda: json.loads(text), "yaml": lambda: yaml.safe_load(text),
                 "lines": lambda: text.splitlines()}[fmt]()
    except (ValueError, yaml.YAMLError) as e:
        raise OutsideError(f"QUERY {node['id']!r}: {name!r} is not valid {fmt}: {e}") from None
    log_event(_log, "query.read", node=node["id"], file=str(name), chars=len(text), format=fmt)
    port = _out_port(node)
    return {port: value} if port else {}


# ---- EMIT ----------------------------------------------------------------------------------------------------
def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _send_file(cfg: Dict, content: str, base_dir: Path, name: Any = None) -> Dict:
    path = _confined(str(name or cfg["file"]), base_dir, cfg.get("allow_dirs"))
    mode = cfg.get("mode", "write")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a" if mode == "append" else "w", encoding="utf-8") as f:
        f.write(content if not (mode == "append" and not content.endswith("\n")) else content + "\n")
    return {"channel": "file", "file": str(path), "bytes": len(content.encode("utf-8")), "mode": mode}


def _send_webhook(cfg: Dict, content: str, subject: str) -> Dict:
    host = urlparse(cfg["url"]).hostname
    if host not in cfg.get("allow_hosts", []):
        raise OutsideError(f"webhook host {host!r} is not in allow_hosts")
    body = json.dumps({"subject": subject, "content": content}).encode("utf-8")
    request = urllib.request.Request(cfg["url"], data=body, method="POST", headers={"Content-Type": "application/json", **(cfg.get("headers") or {})})
    opener = urllib.request.build_opener()                       # no redirects: one could leave the allowlist
    opener.add_handler(_NoRedirect())
    try:
        with opener.open(request, timeout=float(cfg.get("timeout", 15))) as response:
            return {"channel": "webhook", "status": response.status}
    except urllib.error.HTTPError as e:
        raise OutsideError(f"webhook answered {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise OutsideError(f"webhook failed: {e}") from None


def _send_email(cfg: Dict, content: str, subject: str) -> Dict:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["sender"], ", ".join(cfg["recipients"]), subject
    msg.set_content(content)
    host, port = cfg["smtp_host"], int(cfg.get("smtp_port", 587))
    try:
        with smtplib.SMTP(host, port, timeout=float(cfg.get("timeout", 30))) as smtp:
            smtp.starttls()
            user, password = os.environ.get("GRAF_SMTP_USER"), os.environ.get("GRAF_SMTP_PASSWORD")
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise OutsideError(f"e-mail failed: {e}") from None
    return {"channel": "email", "recipients": list(cfg["recipients"])}


def run_emit(node: Dict, in_data: Dict[str, Any], base_dir: Path, effects: bool = True) -> Dict:
    cfg = node.get("config", {})
    channel = cfg.get("channel")
    content = _text(in_data.get("in_content", ""))
    subject = str(in_data.get("in_subject") or cfg.get("subject") or f"GraphLang: {node['id']}")
    if not effects:                                              # a dry run: say what would have happened, change nothing
        receipt = {"channel": channel, "dry_run": True, "chars": len(content)}
        log_event(_log, "emit.dry_run", node=node["id"], channel=channel, chars=len(content))
    else:
        if channel == "file":
            receipt = _send_file(cfg, content, base_dir, in_data.get("in_file"))
        elif channel == "stdout":
            print(content)
            receipt = {"channel": "stdout", "chars": len(content)}
        elif channel == "webhook":
            receipt = _send_webhook(cfg, content, subject)
        elif channel == "email":
            receipt = _send_email(cfg, content, subject)
        else:
            raise OutsideError(f"EMIT {node['id']!r}: unknown channel {channel!r}")
        log_event(_log, "emit.sent", node=node["id"], **{k: v for k, v in receipt.items() if k != "recipients"}, recipients=len(receipt.get("recipients", [])))
    port = _out_port(node)
    return {port: receipt} if port else {}


# ---- OBSERVE -------------------------------------------------------------------------------------------------
def run_observe(node: Dict, in_data: Dict[str, Any], node_output=None, step: int = 0) -> Dict:
    """Record every `in_*` value; hand each on to the `out_*` port of the same name. Never raises: a failed record is a warning."""
    label = node.get("config", {}).get("label") or node["id"]
    values = {k.removeprefix("in_"): v for k, v in in_data.items()}
    try:
        preview = {k: (_text(v)[:OBSERVE_PREVIEW]) for k, v in values.items()}
        log_event(_log, "observe", node=node["id"], label=label, **{f"v_{k}": p for k, p in preview.items()})
        if node_output is not None:
            node_output.observe(step, node["id"], label, values)
    except Exception as e:                                       # noqa: BLE001  observing must never stop the run
        log_event(_log, "observe.failed", level=WARNING, node=node["id"], error=f"{type(e).__name__}: {e}")
    return {f"out_{k}": v for k, v in values.items() if f"out_{k}" in node["ports"]}


# ---- graf validate -------------------------------------------------------------------------------------------
def check_outside(node: Dict, base_dir: Path) -> Tuple[List[str], List[str]]:
    """Static checks for one QUERY, EMIT or OBSERVE node: (errors, warnings)."""
    cfg, ports, typ = node.get("config", {}), node["ports"], node["type"]
    errors: List[str] = []
    warnings: List[str] = []
    allow = cfg.get("allow_dirs")
    if allow is not None and not (isinstance(allow, list) and all(isinstance(d, str) for d in allow)):
        errors.append("allow_dirs must be a list of folders")
        allow = None

    def check_path(key: str = "file") -> Path | None:
        value = cfg.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"needs `{key}` (a path inside the graph's folder)")
            return None
        try:
            target = _confined(value, base_dir, allow)
        except OutsideError as e:
            errors.append(str(e))
            return None
        return target

    if typ == "QUERY":
        if "file" not in cfg and "in_file" not in ports:
            errors.append("needs `file` (or an in_file port)")
        elif "file" in cfg:
            target = check_path()
            if target is not None and not target.exists() and "default" not in cfg:
                warnings.append(f"{cfg['file']!r} does not exist yet; the node fails at run time unless it appears (or a `default` is given)")
        if cfg.get("format", "text") not in QUERY_FORMATS:
            errors.append(f"format must be one of {', '.join(QUERY_FORMATS)}")
        if "tail" in cfg and not (isinstance(cfg["tail"], int) and not isinstance(cfg["tail"], bool) and cfg["tail"] > 0):
            errors.append("tail must be a positive number of lines")
        if _out_port(node) is None:
            errors.append("needs an out_* port for what it reads")
    elif typ == "EMIT":
        channel = cfg.get("channel")
        if channel not in EMIT_CHANNELS:
            errors.append(f"channel must be one of {', '.join(EMIT_CHANNELS)}, not {channel!r}")
        if "in_content" not in ports:
            errors.append("needs an in_content port: the thing to send")
        if channel == "file":
            if "file" in cfg or "in_file" not in ports:
                check_path()
            if cfg.get("mode", "write") not in ("write", "append"):
                errors.append("mode must be write or append")
        elif channel == "webhook":
            url = cfg.get("url")
            hosts = cfg.get("allow_hosts")
            if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https") or not urlparse(url).hostname:
                errors.append("a webhook EMIT needs `url` (http or https)")
            if not (isinstance(hosts, list) and hosts and all(isinstance(h, str) for h in hosts)):
                errors.append("a webhook EMIT needs `allow_hosts`: the host names it may call")
            elif isinstance(url, str) and urlparse(url).hostname not in hosts:
                errors.append(f"url host {urlparse(url).hostname!r} is not in allow_hosts")
        elif channel == "email":
            rec = cfg.get("recipients")
            if not (isinstance(rec, list) and rec and all(isinstance(r, str) and "@" in r for r in rec)):
                errors.append("an e-mail EMIT needs `recipients`: a list of addresses, fixed in the graph")
            for k in ("sender", "smtp_host"):
                if not isinstance(cfg.get(k), str) or not cfg.get(k):
                    errors.append(f"an e-mail EMIT needs `{k}`")
            if "smtp_port" in cfg and not isinstance(cfg["smtp_port"], int):
                errors.append("smtp_port must be a number")
            if not (os.environ.get("GRAF_SMTP_USER") and os.environ.get("GRAF_SMTP_PASSWORD")):
                warnings.append("GRAF_SMTP_USER / GRAF_SMTP_PASSWORD are not set here; set them where the graph runs")
    elif typ == "OBSERVE":
        if not any(p.startswith("in_") for p in ports):
            warnings.append("has no in_* port, so there is nothing to observe")
    return errors, warnings
