package cache

import "github.com/PapaBill1234/phpretro-preservation/internal/localization"

// LocalizedKey makes locale part of the cache identity; non-locale keys cannot collide.
func LocalizedKey(namespace, locale, id string) (string, error) {
	if err := localization.ValidateLocale(locale); err != nil {
		return "", ErrNamespace
	}
	base, err := key(namespace, id)
	if err != nil {
		return "", err
	}
	return base + "locale:" + locale + ":", nil
}
