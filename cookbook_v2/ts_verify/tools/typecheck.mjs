// Type-check the generated TypeScript with the real compiler (strict). Nothing is written to disk.
// stdin:  {"code": text, "function": name, "check_types": bool}
// stdout: {"ok": bool, "checked": bool, "diagnostics": ["line 3, col 9: TS2322: ..."]}
import { extractCode, fail, print, readInput } from "./common.mjs";

const input = readInput();
const code = extractCode(input.code);

if (input.check_types === false || String(input.check_types).toLowerCase() === "false") {
  print({ ok: true, checked: false, diagnostics: [] });
  process.exit(0);
}

let ts;
try {
  ts = (await import("typescript")).default;
} catch {
  fail("typescript is not installed: run `npm install` in cookbook/ts_verify, or pass --param check_types=false");
}

const options = {
  strict: true,
  noEmit: true,
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler,
  lib: ["lib.es2022.d.ts"],     // the language only: no DOM, no Node typings, so the function must be pure
  types: [],
  skipLibCheck: true,
  erasableSyntaxOnly: true,     // what Node can run by stripping types: no enums, namespaces or parameter properties
};
const file = "/virtual/candidate.ts";
const host = ts.createCompilerHost(options, true);
const real = { fileExists: host.fileExists, readFile: host.readFile, getSourceFile: host.getSourceFile };
host.fileExists = (name) => name === file || real.fileExists.call(host, name);
host.readFile = (name) => (name === file ? code : real.readFile.call(host, name));
host.getSourceFile = (name, ...rest) =>
  name === file ? ts.createSourceFile(name, code, ts.ScriptTarget.ES2022, true) : real.getSourceFile.call(host, name, ...rest);

const program = ts.createProgram([file], options, host);
const diagnostics = ts.getPreEmitDiagnostics(program).slice(0, 10).map((d) => {
  const text = ts.flattenDiagnosticMessageText(d.messageText, "\n");
  if (!d.file || d.start === undefined) return `TS${d.code}: ${text}`;
  const { line, character } = d.file.getLineAndCharacterOfPosition(d.start);
  return `line ${line + 1}, col ${character + 1}: TS${d.code}: ${text}`;
});
print({ ok: diagnostics.length === 0, checked: true, diagnostics });
