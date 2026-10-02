// Package account contains the evidence-backed account boundary.
package account

import "errors"

var (
	ErrInvalidCredentials = errors.New("invalid credentials")
	ErrStoreUnavailable   = errors.New("account store unavailable")
)

type User struct {
	ID       string
	Username string
}

type Store interface {
	FindByUsername(username string) (User, string, error)
}

type PasswordVerifier interface {
	Verify(username, password, stored string) bool
}

type Service struct {
	Store    Store
	Verifier PasswordVerifier
}

func (s Service) Authenticate(username, password string) (User, error) {
	if s.Store == nil || s.Verifier == nil {
		return User{}, ErrStoreUnavailable
	}
	user, stored, err := s.Store.FindByUsername(username)
	if err != nil {
		return User{}, ErrStoreUnavailable
	}
	if username == "" || password == "" || !s.Verifier.Verify(user.Username, password, stored) {
		return User{}, ErrInvalidCredentials
	}
	return user, nil
}
