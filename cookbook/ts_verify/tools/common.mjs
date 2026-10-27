// Shared by the ts_verify tools: every tool reads one JSON object on stdin and prints one line of JSON on stdout.
import { readFileSync } from "node:fs";

// Node runs the generated TypeScript by stripping the types (on by default from 22.18 and 23.6) and restricts it with --permission.
// Older versions fail with an obscure "bad option"; say what is wrong instead.
const [major, minor] = process.versions.node.split(".").map(Number);
if (!(major >= 24 || (major === 23 && minor >= 6) || (major === 22 && minor >= 18))) {
  console.error(`ts_verify needs Node 22.18 or newer; this is ${process.version} (${process.execPath}). Put a newer node first on your PATH.`);
  process.exit(1);
}

export function readInput() {
  try {
    return JSON.parse(readFileSync(0, "utf8"));
  } catch (e) {
    fail(`stdin is not JSON: ${e.message}`);
  }
}

// The model usually wraps code in a ``` fence. Take the first fenced block, else the text as it is.
export function extractCode(text) {
  const fenced = /```[a-zA-Z]*\n([\s\S]*?)```/.exec(String(text ?? ""));
  return (fenced ? fenced[1] : String(text ?? "")).trim() + "\n";
}

export function print(value) {
  console.log(JSON.stringify(value));
}

// A tool that cannot run (not a failed check, which is a result) exits 1 with the reason on stderr; the run then stops.
export function fail(message) {
  console.error(message);
  process.exit(1);
}
