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
	cookie := NewCookie("session", "synthetic-token", true, time.Date(2026, 10, 2, 0, 0, 0, 0, time.UTC))
	if !cookie.HttpOnly || !cookie.Secure || cookie.SameSite != http.SameSiteLaxMode {
		t.Fatalf("cookie policy = %#v", cookie)
	}
}
