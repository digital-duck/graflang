"""RECOVER: where an `error` route (design E1) ends up, and what happens next."""

from typing import Dict
from .base import NodeExecutor


class RecoverExecutor(NodeExecutor):
    """Decides what to do after a failure. `config.action`:

    * `halt` (default): this branch ends; the message goes on `out_error`. The run itself finishes normally.
    * `abort`: the run fails with the message.
    * `skip`: carry on from the default control port (`complete`) as if nothing happened.
    * `retry`: send a token out of port `retry` (wire it back to the failed node) up to `max_retries` times, then do
      `config.then` (`halt`, `abort` or `skip`; default `abort`).

    The message is `config.message`, else the text on `in_error` / `in_message` (a node's fallback writes `out_error`).
    """

    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        cfg = node_data.get("config", {})
        nid = node_data["id"]
        action = cfg.get("action", "halt")
        message = cfg.get("message") or in_data.get("in_error") or in_data.get("in_message") or "node failed"
        if action == "retry":
            key = f"_recover.{nid}"
            context[key] = context.get(key, 0) + 1
            if context[key] <= int(cfg.get("max_retries", 1)):
                return {"_route": "retry"}
            action = cfg.get("then", "abort")
        out = {"out_error": message} if "out_error" in node_data["ports"] else {}
        if action == "abort":
            raise RuntimeError(f"RECOVER {nid!r} aborted the run: {message}")
        if action == "halt":
            return {**out, "_halt": True}
        return out                                              # skip: default control port
