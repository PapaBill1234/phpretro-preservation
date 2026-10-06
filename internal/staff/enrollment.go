package staff

import (
	"encoding/base32"
	"errors"
	"strings"
	"sync"
)

var (
	ErrEnrollmentDenied   = errors.New("staff enrollment denied")
	ErrAlreadyEnrolled    = errors.New("staff already enrolled")
	ErrEnrollmentStore    = errors.New("staff enrollment store failure")
	ErrInvalidSecret      = errors.New("invalid synthetic TOTP secret")
	ErrSecretAlreadyBound = errors.New("synthetic TOTP secret already bound")
)

// Principal is a synthetic authorization decision, not a production identity.
type Principal struct {
	ID        string
	Enabled   bool
	CanEnroll bool
}

// EnrollmentAudit is intentionally secret-free.
type EnrollmentAudit struct {
	StaffID string
	Action  string
}

// EnrollmentStore models one atomic secret+audit transaction. Secret state has
// no read API; production protection and schema remain owner/security gates.
type EnrollmentStore struct {
	mu       sync.Mutex
	secrets  map[string]string
	audit    []EnrollmentAudit
	failNext error
}

func NewEnrollmentStore() *EnrollmentStore {
	return &EnrollmentStore{secrets: make(map[string]string)}
}

func (s *EnrollmentStore) Enroll(principal Principal, secret string) error {
	if s == nil || strings.TrimSpace(principal.ID) == "" || !principal.Enabled || !principal.CanEnroll {
		return ErrEnrollmentDenied
	}
	secret = strings.ToUpper(strings.TrimSpace(secret))
	decoded, err := base32.StdEncoding.WithPadding(base32.NoPadding).DecodeString(secret)
	if err != nil || len(decoded) == 0 {
		return ErrInvalidSecret
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.secrets[principal.ID]; exists {
		return ErrAlreadyEnrolled
	}
	for _, bound := range s.secrets {
		if bound == secret {
			return ErrSecretAlreadyBound
		}
	}
	if s.failNext != nil {
		s.failNext = nil
		return ErrEnrollmentStore
	}
	s.secrets[principal.ID] = secret
	s.audit = append(s.audit, EnrollmentAudit{StaffID: principal.ID, Action: "staff.totp.enrolled"})
	return nil
}

// FailNext injects a synthetic storage failure; its detail is never returned.
func (s *EnrollmentStore) FailNext(err error) {
	if s == nil {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.failNext = err
}

func (s *EnrollmentStore) EnrollmentCount() int {
	if s == nil {
		return 0
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.secrets)
}

func (s *EnrollmentStore) AuditRecords() []EnrollmentAudit {
	if s == nil {
		return nil
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]EnrollmentAudit(nil), s.audit...)
}

// String deliberately reports only opaque counts, never secret material.
func (s *EnrollmentStore) String() string {
	return "staff enrollment store"
}

func (r EnrollmentAudit) String() string {
	return r.Action + " staff=" + r.StaffID
}
