package session

import (
	"errors"
	"testing"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/staff"
)

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F37 row; synthetic
// policy is guessed because coordinator approval and captures are absent.
func TestStepUpBindsCodeToSessionAndRateLimitsFailures(t *testing.T) {
	now := time.Unix(1700000000, 0)
	m := &Manager{Now: func() time.Time { return now }, TTL: time.Hour}
	token, err := m.Create("alice")
	if err != nil {
		t.Fatal(err)
	}
	store := &staff.MemoryStore{Records: map[string]staff.Record{"alice": {StaffID: "alice", Secret: "JBSWY3DPEHPK3PXP", Enabled: true}, "bob": {StaffID: "bob", Secret: "JBSWY3DPEHPK3PXP", Enabled: true}}}
	code, err := staff.SyntheticCode(store.Records["alice"].Secret, now)
	if err != nil {
		t.Fatal(err)
	}
	if err := m.StepUp(token, "bob", code, store); !errors.Is(err, ErrStepUpUser) {
		t.Fatalf("got %v", err)
	}
	for i := 0; i < 5; i++ {
		if err := m.StepUp(token, "alice", "000000", store); !errors.Is(err, staff.ErrWrongCode) {
			t.Fatalf("attempt %d: %v", i, err)
		}
	}
	if err := m.StepUp(token, "alice", code, store); !errors.Is(err, ErrStepUpRate) {
		t.Fatalf("got %v, want rate limit", err)
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md, F37 row; library-backed
// current-step validation and successful session-bound step-up are required.
func TestStepUpAcceptsRealCurrentTOTP(t *testing.T) {
	now := time.Unix(1700000000, 0)
	m := &Manager{Now: func() time.Time { return now }, TTL: time.Hour}
	token, err := m.Create("alice")
	if err != nil {
		t.Fatal(err)
	}
	secret := "JBSWY3DPEHPK3PXP"
	code, err := staff.SyntheticCode(secret, now)
	if err != nil {
		t.Fatal(err)
	}
	if err := m.StepUp(token, "alice", code, &staff.MemoryStore{Records: map[string]staff.Record{"alice": {StaffID: "alice", Secret: secret, Enabled: true}}}); err != nil {
		t.Fatal(err)
	}
}
