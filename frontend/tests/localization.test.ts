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
  assert.equal(validateCatalog({ version: "catalog.v0", locale: "en", messages: syntheticCatalogs[0].messages }), false);
  assert.equal(validateCatalog({ version: "catalog.v1", locale: "en US", messages: syntheticCatalogs[0].messages }), false);
});

test("uses deterministic regional, language, then default fallback", () => {
  assert.deepEqual(localeFallbackChain("fr-CA"), ["fr-ca", "fr", "en"]);
  assert.equal(selectCatalog(syntheticCatalogs, "fr-CA")?.locale, "fr");
  assert.equal(selectCatalog(syntheticCatalogs, "de-DE")?.locale, "en");
});

test("matches locale casing without changing the catalog display identifier", () => {
  const catalogs = [{ ...syntheticCatalogs[0], locale: "EN-us" }];
  const model = createLocalizedHomeViewModel(catalogs, "en-US");
  assert.equal(model.locale, "EN-us");
  assert.equal(model.welcome, "Synthetic starter view");
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

test("keeps the home.v1 contract fixed across locale display states", () => {
  const english = createLocalizedHomeViewModel(syntheticCatalogs, "en-US");
  const french = createLocalizedHomeViewModel(syntheticCatalogs, "fr-FR");
  const expectedKeys = ["version", "locale", "siteTitle", "welcome", "navigation"];

  assert.deepEqual(Object.keys(english), expectedKeys);
  assert.deepEqual(Object.keys(french), expectedKeys);
  assert.equal(english.version, "home.v1");
  assert.equal(french.version, "home.v1");
  assert.equal(english.siteTitle, french.siteTitle);
  assert.notEqual(english.welcome, french.welcome);
  assert.notEqual(english.navigation[0]?.label, french.navigation[0]?.label);
  assert.equal(english.navigation[0]?.href, "/");
  assert.equal(french.navigation[0]?.href, "/");
});

test("uses the same deterministic default display state for unknown locales", () => {
  const first = createLocalizedHomeViewModel(syntheticCatalogs, "zz-ZZ");
  const second = createLocalizedHomeViewModel(syntheticCatalogs, "ZZ-zz");

  assert.deepEqual(second, first);
  assert.equal(first.locale, "en");
  assert.equal(first.version, "home.v1");
  assert.deepEqual(first.navigation, [{ label: "Home", href: "/" }]);
});

test("keeps localization presentation-only and rejects capability-shaped additions", () => {
  const displayState = createLocalizedHomeViewModel(syntheticCatalogs, "fr-FR");
  const catalog = syntheticCatalogs.find(({ locale }) => locale === "fr");

  assert.deepEqual(Object.keys(displayState), ["version", "locale", "siteTitle", "welcome", "navigation"]);
  assert.deepEqual(Object.keys(catalog?.messages ?? {}), ["siteTitle", "welcome", "navigationHome"]);
  assert.equal(displayState.navigation.length, 1);
  assert.equal(displayState.navigation[0]?.href, "/");
  assert.equal("route" in displayState, false);
  assert.equal("auth" in displayState, false);
  assert.equal("session" in displayState, false);
  assert.equal("persist" in displayState, false);
  assert.equal("capabilities" in displayState, false);
});
