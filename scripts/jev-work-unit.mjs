#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const value = (name, fallback = undefined) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const inputPath = value("--input");
const outputPath = value("--output", "monitoring/jev-work-unit-results.jsonl");
const cachePath = value("--cache", "monitoring/jev-judgment-cache.json");
const cliPath = value("--cli", process.env.JEV_USE_CLI || "jev-use");
const policyVersion = value("--policy-version", "2026-10-02");

if (!inputPath) {
  console.error("usage: node scripts/jev-work-unit.mjs --input packet.json [--output results.jsonl] [--cache cache.json]");
  process.exit(2);
}

const packet = JSON.parse(fs.readFileSync(inputPath, "utf8"));
if (!packet.unit_id || !packet.state || !Array.isArray(packet.questions) || packet.questions.length === 0) {
  throw new Error("packet requires unit_id, state, and at least one typed question");
}
if (packet.state.length > 120000) throw new Error("state is too large; reduce excerpts before sending to Jev");

const canonical = JSON.stringify({ policyVersion, state: packet.state, questions: packet.questions });
const key = crypto.createHash("sha256").update(canonical).digest("hex");
const readJson = (p, fallback) => fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : fallback;
const cache = readJson(cachePath, {});
const now = new Date().toISOString();
let result;
let cacheHit = false;

if (cache[key]) {
  result = cache[key].result;
  cacheHit = true;
} else {
  const request = JSON.stringify({ state: packet.state, questions: packet.questions, confidence_threshold: 0.5 });
  const run = spawnSync(process.execPath, [cliPath, "judge", request], { encoding: "utf8" });
  if (run.status !== 0) throw new Error(`jev-use judge failed (${run.status}): ${run.stderr || run.stdout}`);
  result = JSON.parse(run.stdout.trim());
  cache[key] = { created_at: now, policy_version: policyVersion, result };
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(cache, null, 2) + "\n");
}

const verdicts = result.verdicts || [];
const highRisk = packet.risk_tier === "high";
const route = verdicts.some((v) => v.escalate || Number(v.confidence) < 0.8)
  ? "sol_review"
  : highRisk ? "jev_high_risk_review" : "eligible_for_source_verification";
const record = {
  recorded_at: now,
  unit_id: packet.unit_id,
  task_class: packet.task_class || "unspecified",
  risk_tier: packet.risk_tier || "routine",
  state_sha256: crypto.createHash("sha256").update(packet.state).digest("hex"),
  judgment_key: key,
  cache_hit: cacheHit,
  candidate_count: packet.candidate_count ?? null,
  batch_size: packet.questions.length,
  route,
  source_refs: packet.source_refs || [],
  result,
};
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.appendFileSync(outputPath, JSON.stringify(record) + "\n");
console.log(JSON.stringify(record, null, 2));
