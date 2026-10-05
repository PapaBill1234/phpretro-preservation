// Package session owns opaque, expiring session state.
package session

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"net/http"
	"sync"
	"time"
)

const LogoutReason = "logout"

var ErrWrongLogoutReason = errors.New("wrong logout reason")

// PublicPage is the post-logout public projection. PrivateField is deliberately
// empty: the public transition does not carry authenticated state.
type PublicPage struct {
	Confirmation string
	PrivateField string
}

type Record struct {
	UserID    string
	ExpiresAt time.Time
}

type Manager struct {
	mu       sync.Mutex
	sessions map[[32]byte]Record
	Now      func() time.Time
	TTL      time.Duration
}

func (m *Manager) now() time.Time {
	if m.Now != nil {
		return m.Now()
	}
	return time.Now().UTC()
}
func (m *Manager) Create(userID string) (string, error) {
	if userID == "" {
		return "", http.ErrNoCookie
	}
	var raw [32]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return "", err
	}
	hash := sha256.Sum256(raw[:])
	m.mu.Lock()
	if m.sessions == nil {
		m.sessions = make(map[[32]byte]Record)
	}
	ttl := m.TTL
	if ttl <= 0 {
		ttl = 30 * time.Minute
	}
	m.sessions[hash] = Record{UserID: userID, ExpiresAt: m.now().Add(ttl)}
	m.mu.Unlock()
	return base64.RawURLEncoding.EncodeToString(raw[:]), nil
}
func (m *Manager) Lookup(token string) (Record, bool) {
	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil || len(raw) != 32 {
		return Record{}, false
	}
	hash := sha256.Sum256(raw)
	m.mu.Lock()
	defer m.mu.Unlock()
	record, ok := m.sessions[hash]
	if !ok || !m.now().Before(record.ExpiresAt) {
		delete(m.sessions, hash)
		return Record{}, false
	}
	return record, true
}
func (m *Manager) Logout(token string) {
	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil || len(raw) != 32 {
		return
	}
	hash := sha256.Sum256(raw)
	m.mu.Lock()
	delete(m.sessions, hash)
	m.mu.Unlock()
}

// LogoutTransition invalidates only the supplied synthetic session and returns
// the logout confirmation. The explicit reason prevents another transition
// from being treated as logout.
func (m *Manager) LogoutTransition(token, reason string) (PublicPage, error) {
	if reason != LogoutReason {
		return PublicPage{}, ErrWrongLogoutReason
	}
	m.Logout(token)
	return PublicPage{Confirmation: "logged out"}, nil
}

// PostLogoutPage is public even if the caller retains the old cookie. Cookie
// names and replacement semantics are unknown; no private field is exposed.
func (m *Manager) PostLogoutPage(token string) PublicPage {
	return PublicPage{}
}

func NewCookie(name, token string, secure bool, now time.Time) *http.Cookie {
	return &http.Cookie{Name: name, Value: token, Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode, Secure: secure, Expires: now.Add(30 * time.Minute), MaxAge: 1800}
}
