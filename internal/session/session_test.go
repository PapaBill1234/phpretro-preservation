package session

import (
	"net/http"
	"testing"
	"time"
)

func TestCreateRotatesAndLooksUp(t *testing.T) {
	now := time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC)
	m := &Manager{Now: func() time.Time { return now }, TTL: time.Hour}
	a, err := m.Create("synthetic-user")
	if err != nil {
		t.Fatal(err)
	}
	b, err := m.Create("synthetic-user")
	if err != nil || a == b {
		t.Fatalf("tokens = %q, %q, %v", a, b, err)
	}
	if _, ok := m.Lookup(a); !ok {
		t.Fatal("new token did not resolve")
	}
}
func TestExpiryAndLogout(t *testing.T) {
	now := time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC)
	m := &Manager{Now: func() time.Time { return now }, TTL: time.Minute}
	token, err := m.Create("synthetic-user")
	if err != nil {
		t.Fatal(err)
	}
	m.Logout(token)
	if _, ok := m.Lookup(token); ok {
		t.Fatal("logged-out token resolved")
	}
	token, _ = m.Create("synthetic-user")
	now = now.Add(2 * time.Minute)
	if _, ok := m.Lookup(token); ok {
		t.Fatal("expired token resolved")
	}
}
func TestCookiePolicy(t *testing.T) {
	cookie := NewCookie("session", "synthetic-token", time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC))
	if !cookie.HttpOnly || !cookie.Secure || cookie.SameSite != http.SameSiteLaxMode {
		t.Fatalf("cookie policy = %#v", cookie)
	}
}

func TestLogoutTransitionInvalidatesOnlySyntheticSessionAndConfirms(t *testing.T) {
	now := time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC)
	m := &Manager{Now: func() time.Time { return now }}
	token, err := m.Create("synthetic-user")
	if err != nil {
		t.Fatal(err)
	}
	page, err := m.LogoutTransition(token, LogoutReason)
	if err != nil {
		t.Fatal(err)
	}
	if page.Confirmation != "logged out" {
		t.Fatalf("confirmation = %q, want %q", page.Confirmation, "logged out")
	}
	if _, ok := m.Lookup(token); ok {
		t.Fatal("logout transition left synthetic session valid")
	}
}

func TestPostLogoutPublicPageExposesNoPrivateField(t *testing.T) {
	m := &Manager{Now: func() time.Time { return time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC) }}
	token, err := m.Create("synthetic-user")
	if err != nil {
		t.Fatal(err)
	}
	m.Logout(token)
	page := m.PostLogoutPage(token)
	if page.PrivateField != "" {
		t.Fatalf("private field = %q, want empty", page.PrivateField)
	}
}

func TestLogoutTransitionRejectsWrongReason(t *testing.T) {
	m := &Manager{Now: func() time.Time { return time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC) }}
	token, err := m.Create("synthetic-user")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := m.LogoutTransition(token, "not-logout"); err != ErrWrongLogoutReason {
		t.Fatalf("error = %v, want %v", err, ErrWrongLogoutReason)
	}
	if _, ok := m.Lookup(token); !ok {
		t.Fatal("wrong reason invalidated synthetic session")
	}
}

func TestPostLogoutPublicPageRejectsRetainedCookiePrivateState(t *testing.T) {
	m := &Manager{Now: func() time.Time { return time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC) }}
	token, err := m.Create("synthetic-user")
	if err != nil {
		t.Fatal(err)
	}
	m.Logout(token)
	page := m.PostLogoutPage(token)
	if page.PrivateField != "" {
		t.Fatalf("retained cookie exposed private field %q", page.PrivateField)
	}
}
