import { strict as assert } from "node:assert";
import test from "node:test";
import { createLocalizedHomeViewModel, syntheticCatalogs } from "../src/localization/index.js";
import { acceptHomeViewModel } from "../src/viewModel.js";

const expectedHomeKeys = ["version", "locale", "siteTitle", "welcome", "navigation"];

test("renders deterministic English and French presentation states", () => {
  const english = createLocalizedHomeViewModel(syntheticCatalogs, "en-US");
  const french = createLocalizedHomeViewModel(syntheticCatalogs, "fr-FR");

  assert.equal(english.locale, "en");
  assert.equal(french.locale, "fr");
  assert.equal(english.siteTitle, "PHPRetro");
  assert.equal(french.siteTitle, "PHPRetro");
  assert.notEqual(english.welcome, french.welcome);
  assert.notEqual(english.navigation[0]?.label, french.navigation[0]?.label);
});

test("uses a deterministic English fallback label for unknown locale casing", () => {
  const first = createLocalizedHomeViewModel(syntheticCatalogs, "zz-ZZ");
  const second = createLocalizedHomeViewModel(syntheticCatalogs, "ZZ-zz");

  assert.deepEqual(second, first);
  assert.equal(first.locale, "en");
  assert.equal(first.welcome, "Synthetic starter view");
  assert.deepEqual(first.navigation, [{ label: "Home", href: "/" }]);
});

test("preserves the typed home.v1 output shape across display states", () => {
  for (const locale of ["en-US", "fr-FR", "unknown"]) {
    const model = createLocalizedHomeViewModel(syntheticCatalogs, locale);
    assert.deepEqual(Object.keys(model), expectedHomeKeys);
    assert.equal(model.version, "home.v1");
    assert.equal(typeof model.locale, "string");
    assert.equal(typeof model.siteTitle, "string");
    assert.equal(typeof model.welcome, "string");
    assert.equal(model.navigation.length, 1);
    assert.equal(model.navigation[0]?.href, "/");
    assert.doesNotThrow(() => acceptHomeViewModel(model));
  }
});

test("keeps navigation stable while locale display strings vary", () => {
  const states = [
    createLocalizedHomeViewModel(syntheticCatalogs, "en-US"),
    createLocalizedHomeViewModel(syntheticCatalogs, "fr-FR"),
    createLocalizedHomeViewModel(syntheticCatalogs, "de-DE")
  ];

  assert.deepEqual(states.map((state) => state.navigation), [
    [{ label: "Home", href: "/" }],
    [{ label: "Accueil", href: "/" }],
    [{ label: "Home", href: "/" }]
  ]);
  assert.notEqual(states[0]?.welcome, states[1]?.welcome);
});

test("contains no route, auth, session, persistence, or capability fields", () => {
  const model = createLocalizedHomeViewModel(syntheticCatalogs, "fr-FR");
  const forbiddenFields = [
    "route", "routes", "auth", "authentication", "session", "persistence",
    "storage", "capability", "capabilities", "token", "user", "permission"
  ];

  assert.deepEqual(Object.keys(model), expectedHomeKeys);
  for (const field of forbiddenFields) {
    assert.equal(Object.hasOwn(model, field), false, `unexpected field: ${field}`);
  }
  assert.deepEqual(Object.keys(model.navigation[0] ?? {}), ["label", "href"]);
});
