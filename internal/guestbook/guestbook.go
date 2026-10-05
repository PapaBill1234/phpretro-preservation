package guestbook

import (
	"context"
	"errors"
	"sync"
)

// ErrForbidden is returned when a viewer cannot access or mutate a guestbook.
var ErrForbidden = errors.New("guestbook access forbidden")

// Entry contains public-to-authorized-viewers guestbook content only.
type Entry struct {
	ID      string
	Widget  string
	Author  string
	Message string
}

// Privacy controls whether non-owners may list entries.
type Privacy struct {
	Private bool
}

// Store keeps synthetic guestbook records. Production schema semantics are
// intentionally unspecified by the available evidence.
type Store struct {
	mu          sync.RWMutex
	entries     map[string]Entry
	privacy     map[string]Privacy
	widgetOwner map[string]string
}

func NewStore() *Store {
	return &Store{
		entries:     make(map[string]Entry),
		privacy:     make(map[string]Privacy),
		widgetOwner: make(map[string]string),
	}
}

// Configure establishes the owner and list privacy for a widget.
func (s *Store) Configure(widget, owner string, privacy Privacy) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.widgetOwner[widget] = owner
	s.privacy[widget] = privacy
}

// List enforces privacy at the server-side storage boundary. A private
// widget is listable only by its owner.
func (s *Store) List(_ context.Context, widget, viewer string) ([]Entry, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	owner := s.widgetOwner[widget]
	if owner == "" || (s.privacy[widget].Private && viewer != owner) {
		return nil, ErrForbidden
	}
	result := make([]Entry, 0)
	for _, entry := range s.entries {
		if entry.Widget == widget {
			result = append(result, entry)
		}
	}
	return result, nil
}

// Add adds an entry only when the named author is the authenticated widget
// owner. Authentication principal semantics remain an integration concern.
func (s *Store) Add(_ context.Context, widget, principal, id, message string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if principal == "" || s.widgetOwner[widget] != principal {
		return ErrForbidden
	}
	s.entries[id] = Entry{ID: id, Widget: widget, Author: principal, Message: message}
	return nil
}

// Delete requires both an entry/widget match and the widget-owner predicate.
func (s *Store) Delete(_ context.Context, widget, principal, id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	entry, ok := s.entries[id]
	if !ok || entry.Widget != widget || principal == "" || s.widgetOwner[widget] != principal {
		return ErrForbidden
	}
	delete(s.entries, id)
	return nil
}
