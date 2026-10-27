// Runs inside the restricted child process. argv: candidate file, function name. stdin: the cases as JSON.
// Node runs this TypeScript directly by stripping the types.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { isDeepStrictEqual } from "node:util";

interface Case { args: unknown[]; expected: unknown }

const [file, name] = process.argv.slice(2) as [string, string];
const cases: Case[] = JSON.parse(readFileSync(0, "utf8"));

let module: Record<string, unknown>;
try {
  module = await import(pathToFileURL(file).href);
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: `cannot load the code: ${(e as Error).message}` }));
  process.exit(0);
}
const fn = module[name];
if (typeof fn !== "function") {
  console.log(JSON.stringify({ ok: false, error: `the module does not export a function named ${name}` }));
  process.exit(0);
}

const failed: Record<string, unknown>[] = [];
for (const c of cases) {
  try {
    const actual = await (fn as (...a: unknown[]) => unknown)(...c.args);
    if (!isDeepStrictEqual(actual, c.expected)) failed.push({ args: c.args, expected: c.expected, actual });
  } catch (e) {
    failed.push({ args: c.args, expected: c.expected, error: String(e) });
  }
}
console.log(JSON.stringify({ ok: failed.length === 0, passed: cases.length - failed.length, total: cases.length, failed: failed.slice(0, 5) }));
