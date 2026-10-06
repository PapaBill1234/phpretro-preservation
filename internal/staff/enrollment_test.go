package staff

import (
	"errors"
	"strings"
	"testing"
	"time"
)

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F36 row (line 54).
// The open owner/security/schema gate means these are synthetic-only contract checks.
func TestSyntheticEnrollmentStore(t *testing.T) {
	store := NewEnrollmentStore()
	p := Principal{ID: "fixture-staff", Enabled: true, CanEnroll: true}
	secret := "JBSWY3DPEHPK3PXP"
	if err := store.Enroll(p, secret); err != nil {
		t.Fatal(err)
	}
	if store.EnrollmentCount() != 1 || len(store.AuditRecords()) != 1 {
		t.Fatal("enrollment and audit were not committed together")
	}
	if err := store.Enroll(p, secret); !errors.Is(err, ErrAlreadyEnrolled) {
		t.Fatalf("duplicate identity enrollment: %v", err)
	}
	if err := store.Enroll(Principal{ID: "other", Enabled: true, CanEnroll: true}, secret); !errors.Is(err, ErrSecretAlreadyBound) {
		t.Fatalf("duplicate secret binding: %v", err)
	}
	if store.EnrollmentCount() != 1 || len(store.AuditRecords()) != 1 {
		t.Fatal("duplicate left partial state")
	}
	if strings.Contains(store.String(), secret) || strings.Contains(store.AuditRecords()[0].String(), secret) {
		t.Fatal("secret exposed by read output")
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F36 row (line 54):
// enrollment must deny disabled/unauthorized staff and leave no partial state.
func TestSyntheticEnrollmentDenialAndFailure(t *testing.T) {
	for _, p := range []Principal{{ID: "disabled", CanEnroll: true}, {ID: "unauthorized", Enabled: true}} {
		s := NewEnrollmentStore()
		if err := s.Enroll(p, "JBSWY3DPEHPK3PXP"); !errors.Is(err, ErrEnrollmentDenied) {
			t.Errorf("denial = %v", err)
		}
		if s.EnrollmentCount() != 0 || len(s.AuditRecords()) != 0 {
			t.Fatal("denial left partial state")
		}
	}
	s := NewEnrollmentStore()
	s.FailNext(errors.New("synthetic db failure with JBSWY3DPEHPK3PXP"))
	if err := s.Enroll(Principal{ID: "staff", Enabled: true, CanEnroll: true}, "JBSWY3DPEHPK3PXP"); !errors.Is(err, ErrEnrollmentStore) {
		t.Fatalf("store error = %v", err)
	} else if strings.Contains(err.Error(), "JBSWY3DPEHPK3PXP") {
		t.Fatal("secret exposed in error")
	}
	if s.EnrollmentCount() != 0 || len(s.AuditRecords()) != 0 {
		t.Fatal("failure left partial state")
	}
	if err := s.Enroll(Principal{ID: "staff", Enabled: true, CanEnroll: true}, "***"); !errors.Is(err, ErrInvalidSecret) {
		t.Fatalf("invalid secret error = %v", err)
	}
	if (*EnrollmentStore)(nil).EnrollmentCount() != 0 || (*EnrollmentStore)(nil).AuditRecords() != nil {
		t.Fatal("nil store reads should be empty")
	}
	(*EnrollmentStore)(nil).FailNext(errors.New("ignored"))
	if err := (*EnrollmentStore)(nil).Enroll(Principal{}, "secret"); !errors.Is(err, ErrEnrollmentDenied) {
		t.Fatalf("nil store error = %v", err)
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F37 row (line 55).
// This only exercises the synthetic validation helper; F37 policy remains gated.
func TestSyntheticCodeValidation(t *testing.T) {
	now := time.Unix(1_700_000_000, 0)
	secret := "JBSWY3DPEHPK3PXP"
	store := &MemoryStore{Records: map[string]Record{"enabled": {StaffID: "enabled", Secret: secret, Enabled: true}, "disabled": {Secret: secret}}}
	code, err := SyntheticCode(secret, now)
	if err != nil || ValidateCode(store, "enabled", code, now) != nil {
		t.Fatalf("synthetic current code: code=%q err=%v", code, err)
	}
	for _, tc := range []struct {
		id, code string
		want     error
	}{{"enabled", "", ErrMissingCode}, {"enabled", "x", ErrMalformedCode}, {"disabled", code, ErrDisabled}, {"absent", code, ErrWrongUser}} {
		if got := ValidateCode(store, tc.id, tc.code, now); !errors.Is(got, tc.want) {
			t.Errorf("ValidateCode(%q): got %v want %v", tc.id, got, tc.want)
		}
	}
	if got := ValidateCode(&MemoryStore{Err: errors.New("unavailable")}, "enabled", code, now); !errors.Is(got, ErrStore) {
		t.Fatalf("store failure = %v", got)
	}
}
