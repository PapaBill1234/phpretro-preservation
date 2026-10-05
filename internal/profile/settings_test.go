package profile

import (
	"errors"
	"testing"
)

type syntheticSettingsStore struct {
	input SettingsInput
	err   error
}

func (s syntheticSettingsStore) FindSettings(int64) (SettingsInput, error) { return s.input, s.err }

func validSettingsInput() SettingsInput {
	return SettingsInput{
		Figure: "hd-1", Gender: "F", Motto: "hello",
		Visibility: "true", ShowOnlineStatus: "false",
		MinimailAlert: "true", FriendRequestAlert: "false",
	}
}

func TestReadSettingsOwnerOnly(t *testing.T) {
	settings, err := (Service{}).ReadSettings(Principal{ID: 7}, 7, syntheticSettingsStore{input: validSettingsInput()})
	if err != nil || settings.Gender != "F" || !settings.Preferences.HomeVisible {
		t.Fatalf("settings = %#v, err = %v", settings, err)
	}
}

func TestReadSettingsRejectsUnauthorizedPrincipal(t *testing.T) {
	_, err := (Service{}).ReadSettings(Principal{ID: 8}, 7, syntheticSettingsStore{input: validSettingsInput()})
	if !errors.Is(err, ErrUnauthorized) {
		t.Fatalf("error = %v", err)
	}
}

func TestValidateSettingsRejectsMalformedFields(t *testing.T) {
	cases := []struct {
		name string
		edit func(*SettingsInput)
		want error
	}{
		{"gender", func(v *SettingsInput) { v.Gender = "X" }, ErrInvalidGender},
		{"figure", func(v *SettingsInput) { v.Figure = "" }, ErrInvalidFigure},
		{"motto", func(v *SettingsInput) { v.Motto = string(make([]rune, 33)) }, ErrInvalidMotto},
		{"preferences", func(v *SettingsInput) { v.Visibility = "maybe" }, ErrInvalidPreferences},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			input := validSettingsInput()
			tc.edit(&input)
			if _, err := ValidateSettings(input, nil); !errors.Is(err, tc.want) {
				t.Fatalf("error = %v, want %v", err, tc.want)
			}
		})
	}
}

func TestReadSettingsReturnsNoValueOnValidationFailure(t *testing.T) {
	input := validSettingsInput()
	input.Figure = ""
	settings, err := (Service{}).ReadSettings(Principal{ID: 7}, 7, syntheticSettingsStore{input: input})
	if !errors.Is(err, ErrInvalidFigure) || settings != (Settings{}) {
		t.Fatalf("settings = %#v, err = %v", settings, err)
	}
}