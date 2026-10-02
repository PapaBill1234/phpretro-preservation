import { strict as assert } from "node:assert";
import test from "node:test";
import { acceptHomeViewModel } from "../src/viewModel.js";
import { phpretroManifest, validateThemeManifest } from "../src/themeManifest.js";

test("accepts the synthetic manifest and rejects capability expansion", () => {
  assert.equal(validateThemeManifest(phpretroManifest), true);
  assert.equal(validateThemeManifest({ ...phpretroManifest, capabilities: ["routes"] }), false);
});

test("rejects unsupported view-model versions", () => {
  assert.throws(() => acceptHomeViewModel({ version: "home.v2" }), /unsupported/);
});

test("rejects malformed view-models", () => {
  assert.throws(() => acceptHomeViewModel({ version: "home.v1", siteTitle: 7 }), /malformed/);
});
