package localization

import (
	"fmt"
	"strings"
)

const (
	CatalogVersion = "catalog.v1"
	DefaultLocale  = "en-US"
)

var SupportedLocales = []string{"en-US", "en-GB", "fr-FR", "fr-CA"}

var messageKeys = map[string]struct{}{
	"home.title":   {},
	"home.welcome": {},
}

type Catalog struct {
	Version  string
	Locale   string
	Messages map[string]string
}

func ValidateCatalog(c Catalog) error {
	if c.Version != CatalogVersion {
		return fmt.Errorf("unsupported catalog version: %q", c.Version)
	}
	if !isSupported(c.Locale) {
		return fmt.Errorf("unsupported locale: %q", c.Locale)
	}
	for key, value := range c.Messages {
		if _, ok := messageKeys[key]; !ok || strings.TrimSpace(value) == "" {
			return fmt.Errorf("malformed message: %q", key)
		}
	}
	return nil
}

// ValidateLocale accepts only a concrete locale from the supported catalog set.
func ValidateLocale(locale string) error {
	if strings.ContainsAny(locale, " 	\r\n") || !isSupported(locale) {
		return fmt.Errorf("unsupported locale: %q", locale)
	}
	return nil
}

// ResolveLocale returns a stable, duplicate-free fallback chain.
func ResolveLocale(requested string) ([]string, error) {
	if requested == "" {
		return []string{DefaultLocale}, nil
	}
	if strings.ContainsAny(requested, " \t\r\n") {
		return nil, fmt.Errorf("malformed locale: %q", requested)
	}
	chain := make([]string, 0, 3)
	if isSupported(requested) {
		chain = append(chain, requested)
	}
	language := strings.SplitN(requested, "-", 2)[0]
	for _, locale := range SupportedLocales {
		if locale != requested && strings.HasPrefix(locale, language+"-") {
			chain = append(chain, locale)
			break
		}
	}
	if !contains(chain, DefaultLocale) {
		chain = append(chain, DefaultLocale)
	}
	return unique(chain), nil
}

// Translate returns false for unknown or missing keys; it never invents text.
func Translate(key string, catalogs []Catalog, requested string) (string, bool) {
	if _, ok := messageKeys[key]; !ok {
		return "", false
	}
	chain, err := ResolveLocale(requested)
	if err != nil {
		return "", false
	}
	for _, locale := range chain {
		for _, catalog := range catalogs {
			if catalog.Locale == locale {
				if value, ok := catalog.Messages[key]; ok && value != "" {
					return value, true
				}
			}
		}
	}
	return "", false
}

func isSupported(locale string) bool { return contains(SupportedLocales, locale) }
func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
func unique(values []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		if !contains(result, value) {
			result = append(result, value)
		}
	}
	return result
}
