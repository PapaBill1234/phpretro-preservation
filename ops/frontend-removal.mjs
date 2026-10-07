// Uses the existing pinned TypeScript parser; adds no application dependency.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const ts = require(process.argv[2]);
const source = readFileSync(0, "utf8");
if (Buffer.byteLength(source) > 4 * 1024 * 1024) throw new Error("source too large");
const tree = ts.createSourceFile(process.argv[3], source, ts.ScriptTarget.Latest, true);
let candidates = 0;
const functions = [];
function scan(node) {
  if ((ts.isFunctionDeclaration(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isMethodDeclaration(node)) && node.body) {
    functions.push(node);
    candidates++;
  }
  ts.forEachChild(node, scan);
}
scan(tree);
if (process.argv[4] === undefined) {
  process.stdout.write(JSON.stringify(Array.from({ length: candidates }, (_, i) => i)));
} else {
  const selected = functions[Number(process.argv[4])];
  if (!selected) throw new Error("invalid function index");
  const body = selected.body;
  const original = source.slice(body.pos, body.end).trimStart();
  // Keep the original body type-checked and imports in use. The runtime result
  // changes without adding a throw or making the program uncompilable.
  const replacement = ts.isBlock(body)
    ? "{ if (true) { return undefined as never; } " + original.slice(1)
    : "{ if (true) { return undefined as never; } return (" + original + "); }";
  process.stdout.write(source.slice(0, body.pos) + " " + replacement + source.slice(body.end));
}
