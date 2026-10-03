package localization

import "testing"

func TestCatalogValidationAndFallback(t *testing.T) {
	catalogs := []Catalog{
		{Version: CatalogVersion, Locale: "fr-FR", Messages: map[string]string{"home.title": "Accueil"}},
		{Version: CatalogVersion, Locale: "en-US", Messages: map[string]string{"home.title": "Home"}},
	}
	for _, catalog := range catalogs {
		if err := ValidateCatalog(catalog); err != nil {
			t.Fatal(err)
		}
	}
	chain, err := ResolveLocale("fr-CA")
	if err != nil || len(chain) != 3 || chain[0] != "fr-CA" || chain[1] != "fr-FR" || chain[2] != "en-US" {
		t.Fatalf("chain=%v err=%v", chain, err)
	}
	if got, ok := Translate("home.title", catalogs, "fr-CA"); !ok || got != "Accueil" {
		t.Fatalf("got=%q ok=%v", got, ok)
	}
	if _, ok := Translate("home.welcome", catalogs, "fr-FR"); ok {
		t.Fatal("missing key was silently substituted")
	}
}

func TestRejectsUnsupportedLocaleAndMalformedMessages(t *testing.T) {
	cases := []Catalog{
		{Version: CatalogVersion, Locale: "xx-XX"},
		{Version: CatalogVersion, Locale: "en-US", Messages: map[string]string{"unknown": "x"}},
		{Version: CatalogVersion, Locale: "en-US", Messages: map[string]string{"home.title": "  "}},
	}
	for _, catalog := range cases {
		if err := ValidateCatalog(catalog); err == nil {
			t.Fatalf("accepted invalid catalog: %#v", catalog)
		}
	}
	if _, err := ResolveLocale("fr FR"); err == nil {
		t.Fatal("accepted malformed requested locale")
	}
}
