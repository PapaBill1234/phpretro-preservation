package session

import (
	"errors"
	"testing"
	"time"
)

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F27 row. The
// fixture explicitly says no security-check/token capture exists; these are
// synthetic-only contract tests for guessed storage and replay semantics.
func TestRememberTokenRejectsExpiry(t *testing.T) {
	now := time.Date(2026, 10, 5, 0, 0, 0, 0, time.UTC)
	store := &RememberTokenStore{Now: func() time.Time { return now }}
	token, err := store.Issue("synthetic-user", "192.0.2.10", time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	now = now.Add(time.Minute)
	if _, err := store.Reauthenticate(token, "192.0.2.10"); !errors.Is(err, ErrRememberTokenExpired) {
		t.Fatalf("error = %v, want expired", err)
	}
}

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F27 row; replay
// behavior is a safety-oriented guess because no token capture exists.
func TestRememberTokenRejectsReplay(t *testing.T) {
	store := &RememberTokenStore{}
	token, err := store.Issue("synthetic-user", "192.0.2.10", time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Reauthenticate(token, "192.0.2.10"); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Reauthenticate(token, "192.0.2.10"); !errors.Is(err, ErrRememberTokenReplay) {
		t.Fatalf("error = %v, want replay", err)
	}
}

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F27 row; IP
// transition handling is explicitly unknown and therefore represented as a
// distinct error rather than silently accepted or rejected as invalid token.
func TestRememberTokenReportsIPTransition(t *testing.T) {
	store := &RememberTokenStore{}
	token, err := store.Issue("synthetic-user", "192.0.2.10", time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Reauthenticate(token, "198.51.100.7"); !errors.Is(err, ErrRememberTokenIPChanged) {
		t.Fatalf("error = %v, want explicit IP transition", err)
	}
}

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F27 row; malformed
// and unknown values must not authenticate.
func TestRememberTokenRejectsUnknownAndMalformedToken(t *testing.T) {
	store := &RememberTokenStore{}
	for _, token := range []string{"not-a-token", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"} {
		if _, err := store.Reauthenticate(token, "192.0.2.10"); !errors.Is(err, ErrRememberTokenInvalid) {
			t.Errorf("token %q error = %v, want invalid", token, err)
		}
	}
}
