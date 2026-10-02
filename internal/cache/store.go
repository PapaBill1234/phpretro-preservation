package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

const (
	NamespaceRead    = "phpretro:cache:read:"
	NamespaceSupport = "phpretro:cache:support:"
	ReadTTL          = 60 * time.Second
	SupportTTL       = 15 * time.Second
)

// MariaDB remains authoritative. Values here are cache-only; outages are misses.
type Store struct{ backend RedisLike }

func New(backend RedisLike) Store { return Store{backend: backend} }
func key(namespace, id string) (string, error) {
	if namespace != NamespaceRead && namespace != NamespaceSupport {
		return "", ErrNamespace
	}
	if id == "" || strings.ContainsAny(id, " \t\r\n") {
		return "", ErrNamespace
	}
	return namespace + id, nil
}
func (s Store) Put(ctx context.Context, namespace, id string, value any, ttl time.Duration) error {
	if s.backend == nil {
		return ErrUnavailable
	}
	k, err := key(namespace, id)
	if err != nil {
		return err
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrSerialization, err)
	}
	if err := s.backend.Set(ctx, k, encoded, ttl); err != nil {
		return err
	}
	return nil
}
func (s Store) Get(ctx context.Context, namespace, id string, out any) (bool, error) {
	if s.backend == nil {
		return false, nil
	}
	k, err := key(namespace, id)
	if err != nil {
		return false, err
	}
	encoded, err := s.backend.Get(ctx, k)
	if err != nil {
		if err == ErrExpired || err == ErrUnavailable {
			return false, nil
		}
		return false, err
	}
	if err := json.Unmarshal(encoded, out); err != nil {
		return false, fmt.Errorf("%w: %v", ErrSerialization, err)
	}
	return true, nil
}
func (s Store) Invalidate(ctx context.Context, namespace, id string) error {
	if s.backend == nil {
		return ErrUnavailable
	}
	k, err := key(namespace, id)
	if err != nil {
		return err
	}
	return s.backend.Delete(ctx, k)
}
