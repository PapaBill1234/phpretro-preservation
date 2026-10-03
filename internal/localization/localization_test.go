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
		{Version: "catalog.v0", Locale: "en-US"},
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
	for _, locale := range []string{"", "en", "en-US\n"} {
		if err := ValidateLocale(locale); err == nil {
			t.Fatalf("accepted invalid concrete locale %q", locale)
		}
	}
}

func TestFallbackIsDeterministicAndDoesNotMutateSupportedLocales(t *testing.T) {
	original := append([]string(nil), SupportedLocales...)
	for i := 0; i < 20; i++ {
		chain, err := ResolveLocale("fr-CA")
		if err != nil {
			t.Fatal(err)
		}
		want := []string{"fr-CA", "fr-FR", "en-US"}
		if len(chain) != len(want) {
			t.Fatalf("iteration %d chain=%v", i, chain)
		}
		for j := range want {
			if chain[j] != want[j] {
				t.Fatalf("iteration %d chain=%v want=%v", i, chain, want)
			}
		}
	}
	for i := range original {
		if SupportedLocales[i] != original[i] {
			t.Fatalf("SupportedLocales mutated: %v", SupportedLocales)
		}
	}
}
