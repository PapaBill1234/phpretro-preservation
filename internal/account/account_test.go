package account

import (
	"errors"
	"testing"
)

type syntheticStore struct {
	user   User
	stored string
	err    error
}

func (s syntheticStore) FindByUsername(string) (User, string, error) { return s.user, s.stored, s.err }

type syntheticVerifier struct{ accepted bool }

func (v syntheticVerifier) Verify(string, string, string) bool { return v.accepted }

func TestAuthenticateSyntheticSuccess(t *testing.T) {
	svc := Service{Store: syntheticStore{user: User{ID: "synthetic-1", Username: "stage3admin"}, stored: "legacy"}, Verifier: syntheticVerifier{accepted: true}}
	got, err := svc.Authenticate("stage3admin", "synthetic-password")
	if err != nil || got.ID != "synthetic-1" {
		t.Fatalf("success = %#v, %v", got, err)
	}
}
func TestAuthenticateRejectsInvalid(t *testing.T) {
	svc := Service{Store: syntheticStore{user: User{ID: "synthetic-1", Username: "stage3admin"}}, Verifier: syntheticVerifier{}}
	if _, err := svc.Authenticate("stage3admin", "wrong"); !errors.Is(err, ErrInvalidCredentials) {
		t.Fatalf("wrong password error = %v", err)
	}
	if _, err := svc.Authenticate("", "wrong"); !errors.Is(err, ErrInvalidCredentials) {
		t.Fatalf("empty username error = %v", err)
	}
}
func TestAuthenticateStoreFailureIsExplicit(t *testing.T) {
	svc := Service{Store: syntheticStore{err: errors.New("synthetic db failure")}, Verifier: syntheticVerifier{accepted: true}}
	if _, err := svc.Authenticate("stage3admin", "password"); !errors.Is(err, ErrStoreUnavailable) {
		t.Fatalf("store error = %v", err)
	}
}
