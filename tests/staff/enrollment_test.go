package staff_test

import (
	"errors"
	"strings"
	"testing"

	"github.com/PapaBill1234/phpretro-preservation/internal/staff"
)

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F36 row (line 54).
// Unknown identity, protection, authorization, and audit schemas are represented only by synthetic fixtures.
func TestEnrollmentBindsSyntheticSecretOnceAndAuditsAtomically(t *testing.T) {
	store := staff.NewEnrollmentStore()
	staffer := staff.Principal{ID: "staff-a", Enabled: true, CanEnroll: true}
	secret := "JBSWY3DPEHPK3PXP"
	if err := store.Enroll(staffer, secret); err != nil {
		t.Fatal(err)
	}
	if err := store.Enroll(staffer, "MZXW6YTB"); !errors.Is(err, staff.ErrAlreadyEnrolled) {
		t.Fatalf("duplicate enrollment error = %v", err)
	}
	if got := store.EnrollmentCount(); got != 1 {
		t.Fatalf("enrollment count = %d", got)
	}
	if err := store.Enroll(staff.Principal{ID: "staff-b", Enabled: true, CanEnroll: true}, secret); !errors.Is(err, staff.ErrSecretAlreadyBound) {
		t.Fatalf("secret reuse error = %v", err)
	}
	if store.EnrollmentCount() != 1 || len(store.AuditRecords()) != 1 {
		t.Fatal("reusing a secret left partial state")
	}
	rows := store.AuditRecords()
	if len(rows) != 1 || rows[0].StaffID != staffer.ID || rows[0].Action != "staff.totp.enrolled" {
		t.Fatalf("audit rows = %#v", rows)
	}
	if strings.Contains(strings.Join([]string{rows[0].Action, rows[0].StaffID}, " "), secret) {
		t.Fatal("secret leaked into audit read")
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F36 row (line 54):
// disabled/unauthorized and duplicate enrollment must be denied without partial state.
func TestEnrollmentDeniesDisabledAndUnauthorizedWithoutState(t *testing.T) {
	for _, principal := range []staff.Principal{
		{ID: "disabled", Enabled: false, CanEnroll: true},
		{ID: "unauthorized", Enabled: true, CanEnroll: false},
	} {
		store := staff.NewEnrollmentStore()
		if err := store.Enroll(principal, "JBSWY3DPEHPK3PXP"); !errors.Is(err, staff.ErrEnrollmentDenied) {
			t.Errorf("principal %#v: got %v", principal, err)
		}
		if store.EnrollmentCount() != 0 || len(store.AuditRecords()) != 0 {
			t.Fatal("denied enrollment left partial state")
		}
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F36 row (line 54):
// duplicate and DB failures cannot leave partial state; secrets must not appear in errors/log output.
func TestEnrollmentFailureIsAtomicAndErrorsAreRedacted(t *testing.T) {
	secret := "JBSWY3DPEHPK3PXP"
	principal := staff.Principal{ID: "staff-a", Enabled: true, CanEnroll: true}
	store := staff.NewEnrollmentStore()
	store.FailNext(errors.New("synthetic database failure containing " + secret))
	if err := store.Enroll(principal, secret); !errors.Is(err, staff.ErrEnrollmentStore) {
		t.Fatalf("error = %v", err)
	} else if strings.Contains(err.Error(), secret) {
		t.Fatal("secret leaked in error")
	}
	if store.EnrollmentCount() != 0 || len(store.AuditRecords()) != 0 {
		t.Fatal("failed enrollment left partial state")
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F36 row (line 54):
// enrollment is secret-bearing but read output and audit records must be redacted.
func TestEnrollmentReadAndAuditNeverExposeSecret(t *testing.T) {
	store := staff.NewEnrollmentStore()
	secret := "JBSWY3DPEHPK3PXP"
	if err := store.Enroll(staff.Principal{ID: "staff-a", Enabled: true, CanEnroll: true}, secret); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(store.String(), secret) {
		t.Fatal("secret leaked in store string output")
	}
	for _, row := range store.AuditRecords() {
		if strings.Contains(row.String(), secret) {
			t.Fatal("secret leaked in audit output")
		}
	}
}
