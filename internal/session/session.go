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

	"github.com/PapaBill1234/phpretro-preservation/internal/staff"
)

const LogoutReason = "logout"

var (
	ErrWrongLogoutReason = errors.New("wrong logout reason")
	ErrStepUpSession     = errors.New("invalid step-up session")
	ErrStepUpUser        = errors.New("step-up user does not match session")
	ErrStepUpRate        = errors.New("step-up rate limit exceeded")
)

// PublicPage is the post-logout public projection. PrivateField is deliberately
// empty: the public transition does not carry authenticated state.
type PublicPage struct {
	Confirmation string
	PrivateField string
}

type Record struct {
	UserID         string
	ExpiresAt      time.Time
	StepUpFailures int
	StepUpWindow   time.Time
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

// StepUp validates a staff TOTP only against the user bound to token.
func (m *Manager) StepUp(token, staffID, code string, store staff.Store) error {
	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil || len(raw) != 32 {
		return ErrStepUpSession
	}
	hash := sha256.Sum256(raw)
	m.mu.Lock()
	record, ok := m.sessions[hash]
	now := m.now()
	if !ok || !now.Before(record.ExpiresAt) {
		m.mu.Unlock()
		return ErrStepUpSession
	}
	if record.UserID != staffID {
		m.mu.Unlock()
		return ErrStepUpUser
	}
	if !record.StepUpWindow.IsZero() && now.Sub(record.StepUpWindow) >= time.Minute {
		record.StepUpFailures = 0
		record.StepUpWindow = now
	}
	if record.StepUpFailures >= 5 {
		m.mu.Unlock()
		return ErrStepUpRate
	}
	m.mu.Unlock()
	if err := staff.ValidateCode(store, staffID, code, now); err != nil {
		m.mu.Lock()
		record, ok = m.sessions[hash]
		if ok {
			if record.StepUpWindow.IsZero() {
				record.StepUpWindow = now
			}
			record.StepUpFailures++
			m.sessions[hash] = record
		}
		m.mu.Unlock()
		return err
	}
	m.mu.Lock()
	if record, ok = m.sessions[hash]; ok {
		record.StepUpFailures = 0
		record.StepUpWindow = time.Time{}
		m.sessions[hash] = record
	}
	m.mu.Unlock()
	return nil
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

// NewCookie requires HTTPS for session transport. Callers cannot downgrade it.
func NewCookie(name, token string, now time.Time) *http.Cookie {
	return &http.Cookie{Name: name, Value: token, Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode, Secure: true, Expires: now.Add(30 * time.Minute), MaxAge: 1800}
}
