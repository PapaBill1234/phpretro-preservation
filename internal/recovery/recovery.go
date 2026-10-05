package recovery

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
	"sync"
)

// Result intentionally does not disclose whether an address is registered.
type Result struct{ Message string }

const genericMessage = "If an account matches, recovery instructions will be sent."

// Identity and Mailer are synthetic-only boundaries; implementations must not contact live systems.
type Identity interface {
	Lookup(context.Context, string) (string, bool, error)
}
type Mailer interface {
	Send(context.Context, string, string) error
}
type Store interface {
	Save(context.Context, string, string) error
	Consume(context.Context, string) (string, bool, error)
}

func Request(ctx context.Context, identity Identity, mailer Mailer, store Store, email string) (Result, error) {
	if err := ctx.Err(); err != nil {
		return Result{}, err
	}
	result := Result{Message: genericMessage}
	id, found, err := identity.Lookup(ctx, strings.ToLower(strings.TrimSpace(email)))
	if err != nil {
		return result, err
	}
	if !found {
		return result, nil
	}
	raw := make([]byte, 32)
	if _, err = rand.Read(raw); err != nil {
		return result, err
	}
	token := hex.EncodeToString(raw)
	digest := sha256.Sum256([]byte(token))
	if err := store.Save(ctx, hex.EncodeToString(digest[:]), id); err != nil {
		return result, err
	}
	if err := mailer.Send(ctx, email, token); err != nil {
		return result, err
	}
	return result, nil
}

func Reset(ctx context.Context, store Store, token string) (bool, error) {
	if token == "" {
		return false, nil
	}
	digest := sha256.Sum256([]byte(token))
	_, ok, err := store.Consume(ctx, hex.EncodeToString(digest[:]))
	return ok, err
}

type MemoryStore struct {
	mu     sync.Mutex
	tokens map[string]string
}

func NewMemoryStore() *MemoryStore { return &MemoryStore{tokens: make(map[string]string)} }
func (s *MemoryStore) Save(ctx context.Context, digest, id string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tokens[digest] = id
	return nil
}
func (s *MemoryStore) Consume(ctx context.Context, digest string) (string, bool, error) {
	if err := ctx.Err(); err != nil {
		return "", false, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	id, ok := s.tokens[digest]
	delete(s.tokens, digest)
	return id, ok, nil
}

var ErrSyntheticOnly = errors.New("recovery requires synthetic fixtures")
