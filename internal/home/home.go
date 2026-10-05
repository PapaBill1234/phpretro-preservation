// Package home contains the synthetic, read-only personal-home boundary.
package home

import (
	"errors"
	"strings"
)

var (
	ErrNotFound         = errors.New("home owner not found")
	ErrStoreUnavailable = errors.New("home store unavailable")
	ErrInvalidLookup    = errors.New("invalid home lookup")
	ErrUnsupportedState = errors.New("unsupported home state")
)

// Lookup identifies an owner by exactly one supported public key.
type Lookup struct {
	Username string
	ID       int64
}

// Record is a synthetic store record. PrivateContent is never exposed to a
// different viewer; its legacy field meaning and backing schema remain UNKNOWN.
type Record struct {
	OwnerID       int64
	Username      string
	ShowHome      bool
	PublicContent string
}

type Store interface {
	FindByID(id int64) (Record, error)
	FindByUsername(username string) (Record, error)
}

type Viewer struct {
	OwnerID int64
}

type View struct {
	OwnerID       int64
	Username      string
	PublicContent string
}

type Service struct{ Store Store }

func (s Service) Read(lookup Lookup, viewer Viewer) (View, error) {
	if s.Store == nil {
		return View{}, ErrStoreUnavailable
	}
	var record Record
	var err error
	switch {
	case lookup.ID > 0 && strings.TrimSpace(lookup.Username) == "":
		record, err = s.Store.FindByID(lookup.ID)
	case lookup.ID == 0 && strings.TrimSpace(lookup.Username) != "":
		record, err = s.Store.FindByUsername(strings.TrimSpace(lookup.Username))
	default:
		return View{}, ErrInvalidLookup
	}
	if err != nil {
		return View{}, err
	}
	if record.OwnerID <= 0 || strings.TrimSpace(record.Username) == "" {
		return View{}, ErrNotFound
	}
	if viewer.OwnerID < 0 {
		return View{}, ErrInvalidLookup
	}
	if !record.ShowHome && viewer.OwnerID != record.OwnerID {
		return View{}, ErrUnsupportedState
	}
	view := View{OwnerID: record.OwnerID, Username: record.Username}
	if record.ShowHome || viewer.OwnerID == record.OwnerID {
		view.PublicContent = record.PublicContent
	}
	return view, nil
}
