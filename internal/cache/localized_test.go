package cache

import "testing"

func TestLocalizedKeyVariesByLocale(t *testing.T) {
	english, err := LocalizedKey(NamespaceRead, "en-US", "home")
	if err != nil {
		t.Fatal(err)
	}
	french, err := LocalizedKey(NamespaceRead, "fr-FR", "home")
	if err != nil {
		t.Fatal(err)
	}
	plain, err := key(NamespaceRead, "home")
	if err != nil {
		t.Fatal(err)
	}
	if english == french || english == plain || french == plain {
		t.Fatalf("keys collide: %q %q %q", english, french, plain)
	}
	for _, locale := range []string{"", "fr FR", "xx-XX"} {
		if _, err := LocalizedKey(NamespaceRead, locale, "home"); err != ErrNamespace {
			t.Fatalf("locale=%q err=%v", locale, err)
		}
	}
}
func TestLocalizedKeyCanonicalIdentitySeparatesPlainKey(t *testing.T) {
	plain, err := key(NamespaceSupport, "session")
	if err != nil {
		t.Fatal(err)
	}
	localized, err := LocalizedKey(NamespaceSupport, "en-US", "session")
	if err != nil {
		t.Fatal(err)
	}
	if plain != NamespaceSupport+"session" {
		t.Fatalf("plain=%q", plain)
	}
	if localized != NamespaceSupport+"sessionlocale:en-US:" {
		t.Fatalf("localized=%q", localized)
	}
	if localized == plain {
		t.Fatalf("localized key collided with plain key: %q", localized)
	}
}

func TestLocalizedKeySeparatesSimilarSyntheticIdentities(t *testing.T) {
	cases := []struct{ locale, id string }{{"en-US", "home"}, {"en-GB", "home"}, {"fr-FR", "home"}, {"en-US", "home:locale:en-GB:"}}
	seen := make(map[string]string, len(cases))
	for _, tc := range cases {
		got, err := LocalizedKey(NamespaceRead, tc.locale, tc.id)
		if err != nil {
			t.Fatal(err)
		}
		identity := tc.locale + "|" + tc.id
		if previous, ok := seen[got]; ok {
			t.Fatalf("identities %q and %q collided as %q", previous, identity, got)
		}
		seen[got] = identity
	}
}

func TestLocalizedKeySeparatesCanonicalLocaleVariants(t *testing.T) {
	keys := make(map[string]string)
	for _, locale := range []string{"en-US", "en-GB", "fr-FR", "fr-CA"} {
		key, err := LocalizedKey(NamespaceRead, locale, "home")
		if err != nil {
			t.Fatalf("locale=%q err=%v", locale, err)
		}
		if previous, exists := keys[key]; exists {
			t.Fatalf("locales %q and %q collided at %q", previous, locale, key)
		}
		keys[key] = locale
	}
	if _, err := LocalizedKey(NamespaceRead, "en-us", "home"); err != ErrNamespace {
		t.Fatalf("non-canonical locale was accepted: %v", err)
	}
}
