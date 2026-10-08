package staff_test

import (
	"encoding/base32"
	"errors"
	"testing"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/staff"
)

// Evidence: docs/evidence/QA3-totp-vectors.md; RFC 4226 counter 1 is 287082.
func TestValidateCodeAcceptsCurrentAndBindsPerStaff(t *testing.T) {
	now := time.Unix(59, 0)
	store := vectorStore()
	code := "287082"
	if err := staff.ValidateCode(store, "alice", code, now); err != nil {
		t.Fatal(err)
	}
	if err := staff.ValidateCode(store, "bob", code, now); !errors.Is(err, staff.ErrWrongCode) {
		t.Fatalf("got %v, want wrong-code rejection for another staff member", err)
	}
}
func TestValidateRejectsCases(t *testing.T) {
	// Evidence: docs/evidence/QA3-totp-vectors.md; fixed current-step vector.
	now := time.Unix(59, 0)
	s := vectorStore()
	s.Records["off"] = staff.Record{StaffID: "off", Secret: vectorSecret(), Enabled: false}
	s.Records["on"] = staff.Record{StaffID: "on", Secret: vectorSecret(), Enabled: true}
	code := "287082"
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

// Evidence: docs/evidence/QA3-totp-vectors.md; synthetic identity binding policy.
func TestValidateRejectsEmptyAndMismatchedStoreIdentity(t *testing.T) {
	now := time.Unix(59, 0)
	secret := vectorSecret()
	code := "287082"
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

// Evidence: docs/evidence/QA3-totp-vectors.md; RFC 6238 Appendix B SHA1 vectors.
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

// Evidence: docs/evidence/QA3-totp-vectors.md; RFC 4226 counters 0, 2 and 3
// with the existing synthetic zero-skew policy (not captured legacy behavior).
func TestAdjacentStepsAreRejected(t *testing.T) {
	now := time.Unix(59, 0)
	store := vectorStore()
	for _, code := range []string{"755224", "359152"} {
		if err := staff.ValidateCode(store, "alice", code, now); !errors.Is(err, staff.ErrExpiredCode) {
			t.Fatalf("code %s: got %v, want expired", code, err)
		}
	}
	if err := staff.ValidateCode(store, "alice", "969429", now); !errors.Is(err, staff.ErrWrongCode) {
		t.Fatalf("outside adjacent window: got %v, want wrong", err)
	}
}

func vectorSecret() string {
	return base32.StdEncoding.WithPadding(base32.NoPadding).EncodeToString([]byte("12345678901234567890"))
}

func vectorStore() *staff.MemoryStore {
	return &staff.MemoryStore{Records: map[string]staff.Record{
		"alice": {StaffID: "alice", Secret: vectorSecret(), Enabled: true},
		"bob":   {StaffID: "bob", Secret: base32.StdEncoding.WithPadding(base32.NoPadding).EncodeToString([]byte("abcdefghijklmnopqrst")), Enabled: true},
	}}
}

func TestValidateIndependentRFC6238Vectors(t *testing.T) {
	// Evidence: docs/evidence/QA3-totp-vectors.md, Appendix B fixed SHA1 values.
	for _, tc := range []struct {
		at   int64
		code string
	}{
		{59, "287082"}, {1111111109, "081804"}, {1111111111, "050471"},
		{1234567890, "005924"}, {2000000000, "279037"}, {20000000000, "353130"},
	} {
		if err := staff.ValidateCode(vectorStore(), "alice", tc.code, time.Unix(tc.at, 0)); err != nil {
			t.Fatalf("RFC timestamp %d: %v", tc.at, err)
		}
	}
}

func TestNilStoreFailsClosed(t *testing.T) {
	// Evidence: docs/evidence/QA3-totp-vectors.md; unavailable store cannot authorize.
	for _, store := range []staff.Store{nil, (*staff.MemoryStore)(nil)} {
		if err := staff.ValidateCode(store, "alice", "287082", time.Unix(59, 0)); !errors.Is(err, staff.ErrStore) {
			t.Fatalf("nil store: got %v", err)
		}
	}
}
