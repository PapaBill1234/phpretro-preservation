package staff_test

import (
	"encoding/base32"
	"errors"
	"github.com/PapaBill1234/phpretro-preservation/internal/staff"
	"testing"
	"time"
)

// Evidence basis: no capture or fixture was supplied; synthetic behavior is
// guessed, as recorded in docs/units/QA1.md.
func TestValidateCodeAcceptsCurrentAndBindsPerStaff(t *testing.T) {
	now := time.Unix(1_700_000_000, 0)
	store := &staff.MemoryStore{Records: map[string]staff.Record{"alice": {StaffID: "alice", Secret: "JBSWY3DPEHPK3PXP", Enabled: true}, "bob": {StaffID: "bob", Secret: "KRUGS4ZANFZSAYJA", Enabled: true}}}
	code, err := staff.SyntheticCode(store.Records["alice"].Secret, now)
	if err != nil {
		t.Fatal(err)
	}
	if err := staff.ValidateCode(store, "alice", code, now); err != nil {
		t.Fatal(err)
	}
	if err := staff.ValidateCode(store, "bob", code, now); !errors.Is(err, staff.ErrWrongCode) {
		t.Fatalf("got %v, want wrong-code rejection for another staff member", err)
	}
}
func TestValidateRejectsCases(t *testing.T) {
	now := time.Unix(1_700_000_000, 0)
	s := &staff.MemoryStore{Records: map[string]staff.Record{"off": {StaffID: "off", Secret: "JBSWY3DPEHPK3PXP"}, "on": {StaffID: "on", Secret: "JBSWY3DPEHPK3PXP", Enabled: true}}}
	code, _ := staff.SyntheticCode(s.Records["on"].Secret, now)
	cases := []struct {
		name, id, code string
		at             time.Time
		want           error
	}{{"missing", "on", "", now, staff.ErrMissingCode}, {"disabled", "off", code, now, staff.ErrDisabled}, {"malformed", "on", "abc", now, staff.ErrMalformedCode}, {"wrong", "on", "000000", now, staff.ErrWrongCode}, {"expired", "on", code, now.Add(30 * time.Second), staff.ErrExpiredCode}, {"wrong-user", "unknown", code, now, staff.ErrWrongUser}}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if err := staff.ValidateCode(s, tc.id, tc.code, tc.at); !errors.Is(err, tc.want) {
				t.Fatalf("got %v want %v", err, tc.want)
			}
		})
	}
}

// Evidence basis: no capture or fixture was supplied; rejecting a store
// identity mismatch is the guessed security contract recorded in docs/units/QA1.md.
func TestValidateRejectsEmptyAndMismatchedStoreIdentity(t *testing.T) {
	now := time.Unix(1_700_000_000, 0)
	secret := "JBSWY3DPEHPK3PXP"
	code, err := staff.SyntheticCode(secret, now)
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		name   string
		record staff.Record
	}{
		{name: "empty", record: staff.Record{Secret: secret, Enabled: true}},
		{name: "bob returned for alice", record: staff.Record{StaffID: "bob", Secret: secret, Enabled: true}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			store := &staff.MemoryStore{Records: map[string]staff.Record{"alice": tc.record}}
			if err := staff.ValidateCode(store, "alice", code, now); !errors.Is(err, staff.ErrWrongUser) {
				t.Fatalf("got %v want %v", err, staff.ErrWrongUser)
			}
		})
	}
}

func TestStoreErrorFailsClosed(t *testing.T) {
	if err := staff.ValidateCode(&staff.MemoryStore{Err: errors.New("down")}, "alice", "123456", time.Now()); !errors.Is(err, staff.ErrStore) {
		t.Fatal(err)
	}
}

// Evidence basis: RFC 6238 Appendix B, SHA1 test vectors (time 59, 8 digits).
func TestExternalRFC6238VectorAndConfiguredParameters(t *testing.T) {
	secret := base32.StdEncoding.WithPadding(base32.NoPadding).EncodeToString([]byte("12345678901234567890"))
	got, err := staff.SyntheticCode(secret, time.Unix(59, 0))
	if err != nil {
		t.Fatal(err)
	}
	// SyntheticCode's configured contract is 6 digits and a 30-second period;
	// compare a six-digit RFC computation at its corresponding counter directly.
	if got != "287082" { // RFC 6238 Appendix B: 94287082 truncated to configured 6 digits.
		t.Fatalf("got %q, want RFC-derived 287082", got)
	}
}

// Evidence basis: synthetic timing policy only; no retained capture establishes skew.
func TestAdjacentStepsAreRejected(t *testing.T) {
	now := time.Unix(1_700_000_010, 0)
	secret := "JBSWY3DPEHPK3PXP"
	store := &staff.MemoryStore{Records: map[string]staff.Record{"alice": {StaffID: "alice", Secret: secret, Enabled: true}}}
	for _, delta := range []time.Duration{-30 * time.Second, 30 * time.Second} {
		code, err := staff.SyntheticCode(secret, now.Add(delta))
		if err != nil {
			t.Fatal(err)
		}
		if err := staff.ValidateCode(store, "alice", code, now); !errors.Is(err, staff.ErrExpiredCode) {
			t.Fatalf("delta %s: got %v, want expired", delta, err)
		}
	}
}
