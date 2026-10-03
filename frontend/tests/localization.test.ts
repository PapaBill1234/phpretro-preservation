import { strict as assert } from "node:assert";
import test from "node:test";
import {
  createLocalizedHomeViewModel,
  localeFallbackChain,
  missingKey,
  selectCatalog,
  syntheticCatalogs,
  translate,
  validateCatalog
} from "../src/localization/index.js";

test("validates the typed catalog shape and rejects extra or missing keys", () => {
  assert.equal(validateCatalog(syntheticCatalogs[0]), true);
  assert.equal(validateCatalog({ locale: "xx", messages: { siteTitle: "x", welcome: "x" } }), false);
  assert.equal(validateCatalog({ locale: "xx", messages: { siteTitle: "x", welcome: "x", navigationHome: "x", extra: "x" } }), false);
});

test("uses deterministic regional, language, then default fallback", () => {
  assert.deepEqual(localeFallbackChain("fr-CA"), ["fr-ca", "fr", "en"]);
  assert.equal(selectCatalog(syntheticCatalogs, "fr-CA")?.locale, "fr");
  assert.equal(selectCatalog(syntheticCatalogs, "de-DE")?.locale, "en");
});

test("makes missing keys explicit without hiding them", () => {
  assert.equal(missingKey("welcome"), "[missing:welcome]");
  assert.equal(translate(undefined, "welcome"), "[missing:welcome]");
  assert.throws(() => translate(undefined, "welcome", "throw"), /missing localization key/);
});

test("builds a localized home view model", () => {
  const model = createLocalizedHomeViewModel(syntheticCatalogs, "fr-CA");
  assert.equal(model.locale, "fr");
  assert.equal(model.welcome, "Vue de démarrage synthétique");
  assert.deepEqual(model.navigation, [{ label: "Accueil", href: "/" }]);
});
