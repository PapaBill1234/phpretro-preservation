package registration

import (
	"context"
	"errors"
	"fmt"
	"net/mail"
	"regexp"
	"strings"
	"sync"
)

type Input struct {
	Username string
	Email    string
	Age      int
	Consent  bool
}

type User struct {
	ID       string
	Username string
	Email    string
}

type AuditEvent struct {
	UserID string
	Action string
}

type Store interface {
	CreateWithAudit(context.Context, User, AuditEvent) error
}

var usernamePattern = regexp.MustCompile(`^[a-zA-Z0-9_]{3,24}$`)

// Validation policy is a conservative guess: no registration capture or concrete
// field/security contract is retained (docs/roadmap/F18-F30-feature-approval.md, F25).
func Validate(in Input) error {
	if !usernamePattern.MatchString(in.Username) {
		return errors.New("username must be 3-24 ASCII letters, digits, or underscores")
	}
	address, err := mail.ParseAddress(in.Email)
	if err != nil || address.Address != in.Email || !strings.Contains(in.Email, ".") || !strings.HasSuffix(in.Email, ".test") {
		return errors.New("email must be a synthetic .test address")
	}
	if in.Age < 13 || in.Age > 120 {
		return errors.New("age is outside the accepted range")
	}
	if !in.Consent {
		return errors.New("consent is required")
	}
	return nil
}

func Create(ctx context.Context, store Store, in Input) (User, error) {
	if err := Validate(in); err != nil {
		return User{}, err
	}
	if err := ctx.Err(); err != nil {
		return User{}, err
	}
	user := User{ID: "synthetic-" + in.Username, Username: in.Username, Email: in.Email}
	event := AuditEvent{UserID: user.ID, Action: "account.registered"}
	if err := store.CreateWithAudit(ctx, user, event); err != nil {
		return User{}, fmt.Errorf("create registration: %w", err)
	}
	return user, nil
}

// MemoryStore is a synthetic transactional store; the lock makes insertion of
// both records indivisible to readers.
type MemoryStore struct {
	mu        sync.Mutex
	users     []User
	audits    []AuditEvent
	FailAudit error
}

func NewMemoryStore() *MemoryStore { return &MemoryStore{} }

func (s *MemoryStore) CreateWithAudit(ctx context.Context, user User, event AuditEvent) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.FailAudit != nil {
		return s.FailAudit
	}
	for _, existing := range s.users {
		if existing.Username == user.Username || existing.Email == user.Email {
			return errors.New("account already exists")
		}
	}
	s.users = append(s.users, user)
	s.audits = append(s.audits, event)
	return nil
}

func (s *MemoryStore) Snapshot() ([]User, []AuditEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]User(nil), s.users...), append([]AuditEvent(nil), s.audits...)
}
