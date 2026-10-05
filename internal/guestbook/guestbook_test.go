package guestbook

import (
	"context"
	"errors"
	"testing"
)

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F28 row: the
// legacy list lacks an evident privacy gate, while schema/helper semantics
// are unknown. These synthetic tests encode a conservative guessed contract.
func TestPrivateListIsDeniedForNonOwnerAndHasNoPrivateFields(t *testing.T) {
	store := NewStore()
	store.Configure("widget-1", "owner-1", Privacy{Private: true})
	if err := store.Add(context.Background(), "widget-1", "owner-1", "entry-1", "synthetic secret"); err != nil {
		t.Fatal(err)
	}
	entries, err := store.List(context.Background(), "widget-1", "viewer-2")
	if !errors.Is(err, ErrForbidden) {
		t.Fatalf("non-owner list err = %v, want ErrForbidden", err)
	}
	if len(entries) != 0 {
		t.Fatalf("non-owner received entries: %#v", entries)
	}
}

// Evidence basis: the same F28 row identifies private guestbook access as
// unknown; owner visibility is the conservative synthetic counterpart.
func TestPrivateListAllowsOwner(t *testing.T) {
	store := NewStore()
	store.Configure("widget-1", "owner-1", Privacy{Private: true})
	if err := store.Add(context.Background(), "widget-1", "owner-1", "entry-1", "hello"); err != nil {
		t.Fatal(err)
	}
	entries, err := store.List(context.Background(), "widget-1", "owner-1")
	if err != nil || len(entries) != 1 || entries[0].Message != "hello" {
		t.Fatalf("owner list = %#v, %v; want one entry", entries, err)
	}
}

// Evidence basis: the F28 row says the legacy delete query has no widget-owner
// predicate. This assertion requires that only the configured owner deletes.
func TestDeleteRequiresWidgetOwner(t *testing.T) {
	store := NewStore()
	store.Configure("widget-1", "owner-1", Privacy{})
	if err := store.Add(context.Background(), "widget-1", "owner-1", "entry-1", "hello"); err != nil {
		t.Fatal(err)
	}
	if err := store.Delete(context.Background(), "widget-1", "viewer-2", "entry-1"); !errors.Is(err, ErrForbidden) {
		t.Fatalf("non-owner delete err = %v, want ErrForbidden", err)
	}
	entries, err := store.List(context.Background(), "widget-1", "owner-1")
	if err != nil || len(entries) != 1 {
		t.Fatalf("entry after denied delete = %#v, %v; want preserved", entries, err)
	}
	if err := store.Delete(context.Background(), "widget-1", "owner-1", "entry-1"); err != nil {
		t.Fatalf("owner delete: %v", err)
	}
}

// Evidence basis: the F28 row identifies add/configure helper and schema
// semantics as unknown; reject unauthenticated writes under this guessed rule.
func TestAddRejectsNonOwner(t *testing.T) {
	store := NewStore()
	store.Configure("widget-1", "owner-1", Privacy{})
	if err := store.Add(context.Background(), "widget-1", "viewer-2", "entry-1", "no"); !errors.Is(err, ErrForbidden) {
		t.Fatalf("non-owner add err = %v, want ErrForbidden", err)
	}
}
