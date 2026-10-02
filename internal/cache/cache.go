package cache

import (
	"context"
	"errors"
	"time"
)

var (
	ErrUnavailable   = errors.New("cache unavailable")
	ErrNamespace     = errors.New("invalid cache namespace")
	ErrExpired       = errors.New("cache entry expired")
	ErrSerialization = errors.New("cache serialization failure")
)

type RedisLike interface {
	Get(context.Context, string) ([]byte, error)
	Set(context.Context, string, []byte, time.Duration) error
	Delete(context.Context, string) error
}

// Memory is a deterministic, outage-capable RedisLike test double.
type Memory struct {
	now  time.Time
	data map[string]entry
	Down bool
}
type entry struct {
	value   []byte
	expires time.Time
}

func NewMemory(now time.Time) *Memory     { return &Memory{now: now, data: make(map[string]entry)} }
func (m *Memory) Advance(d time.Duration) { m.now = m.now.Add(d) }
func (m *Memory) Get(_ context.Context, key string) ([]byte, error) {
	if m.Down {
		return nil, ErrUnavailable
	}
	e, ok := m.data[key]
	if !ok {
		return nil, ErrExpired
	}
	if !e.expires.IsZero() && !m.now.Before(e.expires) {
		delete(m.data, key)
		return nil, ErrExpired
	}
	return append([]byte(nil), e.value...), nil
}
func (m *Memory) Set(_ context.Context, key string, value []byte, ttl time.Duration) error {
	if m.Down {
		return ErrUnavailable
	}
	if ttl <= 0 {
		return ErrExpired
	}
	m.data[key] = entry{value: append([]byte(nil), value...), expires: m.now.Add(ttl)}
	return nil
}
func (m *Memory) Delete(_ context.Context, key string) error {
	if m.Down {
		return ErrUnavailable
	}
	delete(m.data, key)
	return nil
}
