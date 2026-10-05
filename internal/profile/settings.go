package profile

import (
	"errors"
	"strings"
	"unicode"
	"unicode/utf8"
)

var (
	ErrUnauthorized       = errors.New("profile settings unauthorized")
	ErrInvalidFigure      = errors.New("invalid profile figure")
	ErrInvalidMotto       = errors.New("invalid profile motto")
	ErrInvalidPreferences = errors.New("invalid profile preferences")
)

// Settings contains the profile-owned appearance and preference values exposed
// by the settings read boundary. It deliberately has no persistence methods.
type Settings struct {
	Figure      string
	Gender      string
	Motto       string
	Preferences Preferences
}

// Preferences is the bounded set of preference values identified by the
// source contract. The fields are booleans because the source does not provide
// a separate enum or persistence schema for them.
type Preferences struct {
	HomeVisible   bool
	OnlineVisible bool
	MinimailAlertsEnabled bool
	FriendRequestAlertsEnabled bool
}

type Principal struct {
	ID int64
}

// SettingsInput mirrors the source's posted values without assigning a
// database schema to them.
type SettingsInput struct {
	Figure             string
	Gender             string
	Motto              string
	Visibility         string
	ShowOnlineStatus   string
	MinimailAlert      string
	FriendRequestAlert string
}

type SettingsStore interface {
	FindSettings(profileID int64) (SettingsInput, error)
}

// ReadSettings reads settings only for the authenticated owner. No write,
// audit, session, CSRF, or persistence behavior is implied by this method.
func (s Service) ReadSettings(principal Principal, profileID int64, store SettingsStore) (Settings, error) {
	if principal.ID <= 0 || profileID <= 0 || principal.ID != profileID {
		return Settings{}, ErrUnauthorized
	}
	if store == nil {
		return Settings{}, ErrStoreUnavailable
	}
	return ValidateSettings(store.FindSettings(profileID))
}

func ValidateSettings(input SettingsInput, err error) (Settings, error) {
	if err != nil {
		return Settings{}, err
	}
	if strings.TrimSpace(input.Figure) == "" || hasControl(input.Figure) {
		return Settings{}, ErrInvalidFigure
	}
	if input.Gender != "M" && input.Gender != "F" {
		return Settings{}, ErrInvalidGender
	}
	if utf8.RuneCountInString(input.Motto) > 32 || hasControl(input.Motto) {
		return Settings{}, ErrInvalidMotto
	}
	preferences, ok := parsePreferences(input)
	if !ok {
		return Settings{}, ErrInvalidPreferences
	}
	return Settings{Figure: input.Figure, Gender: input.Gender, Motto: input.Motto, Preferences: preferences}, nil
}

func parsePreferences(input SettingsInput) (Preferences, bool) {
	values := []string{input.Visibility, input.ShowOnlineStatus, input.MinimailAlert, input.FriendRequestAlert}
	parsed := make([]bool, len(values))
	for i, value := range values {
		switch value {
		case "true":
			parsed[i] = true
		case "false":
		default:
			return Preferences{}, false
		}
	}
	return Preferences{HomeVisible: parsed[0], OnlineVisible: parsed[1], MinimailAlertsEnabled: parsed[2], FriendRequestAlertsEnabled: parsed[3]}, true
}

func hasControl(value string) bool {
	for _, r := range value {
		if unicode.IsControl(r) {
			return true
		}
	}
	return false
}
