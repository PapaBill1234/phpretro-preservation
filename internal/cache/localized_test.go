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
