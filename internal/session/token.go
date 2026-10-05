// Package session owns synthetic session and remember-token state.
package session

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"sync"
	"time"
)

var (
	ErrRememberTokenInvalid   = errors.New("invalid remember token")
	ErrRememberTokenExpired   = errors.New("remember token expired")
	ErrRememberTokenReplay    = errors.New("remember token already used")
	ErrRememberTokenIPChanged = errors.New("remember token IP changed")
)

type rememberRecord struct {
	userID    string
	ip        string
	expiresAt time.Time
	used      bool
}

// RememberTokenStore is an in-memory, synthetic-only implementation. Exact
// storage, expiry and replay behavior are guesses: F27 has no direct capture.
type RememberTokenStore struct {
	mu     sync.Mutex
	tokens map[[32]byte]rememberRecord
	Now    func() time.Time
}

func (s *RememberTokenStore) now() time.Time {
	if s.Now != nil {
		return s.Now()
	}
	return time.Now().UTC()
}

// Issue creates a cryptographically random opaque token and stores only its hash.
func (s *RememberTokenStore) Issue(userID, ip string, ttl time.Duration) (string, error) {
	if userID == "" || ip == "" || ttl <= 0 {
		return "", ErrRememberTokenInvalid
	}
	var raw [32]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return "", err
	}
	hash := sha256.Sum256(raw[:])
	s.mu.Lock()
	if s.tokens == nil {
		s.tokens = make(map[[32]byte]rememberRecord)
	}
	s.tokens[hash] = rememberRecord{userID: userID, ip: ip, expiresAt: s.now().Add(ttl)}
	s.mu.Unlock()
	return base64.RawURLEncoding.EncodeToString(raw[:]), nil
}

// Reauthenticate consumes the token on successful use. An IP mismatch is
// explicit and does not consume the token, allowing policy at the caller boundary.
func (s *RememberTokenStore) Reauthenticate(token, ip string) (string, error) {
	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil || len(raw) != 32 {
		return "", ErrRememberTokenInvalid
	}
	hash := sha256.Sum256(raw)
	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.tokens[hash]
	if !ok {
		return "", ErrRememberTokenInvalid
	}
	if !s.now().Before(record.expiresAt) {
		delete(s.tokens, hash)
		return "", ErrRememberTokenExpired
	}
	if record.used {
		return "", ErrRememberTokenReplay
	}
	if ip != record.ip {
		return "", ErrRememberTokenIPChanged
	}
	record.used = true
	s.tokens[hash] = record
	return record.userID, nil
}
