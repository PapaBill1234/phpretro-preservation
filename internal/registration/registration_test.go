package registration

import (
	"context"
	"errors"
	"testing"
)

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F25 (line 43)
// explicitly says registration capture is absent and validation/security contracts
// remain unspecified; these malformed-input cases are conservative synthetic guesses.
func TestValidateRejectsMalformedInput(t *testing.T) {
	cases := []Input{
		{},
		{Username: "x", Email: "not-an-email", Age: 20, Consent: true},
		{Username: "x", Email: "person@example.test", Age: 20, Consent: true},
		{Username: "valid_name", Email: "person@example.test", Age: 12, Consent: true},
		{Username: "valid_name", Email: "person@example.test", Age: 20, Consent: false},
	}
	for _, input := range cases {
		if err := Validate(input); err == nil {
			t.Errorf("Validate(%+v) unexpectedly succeeded", input)
		}
	}
}

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F25 (line 43)
// names user creation and transactions but provides no schema or capture; verify
// atomicity and auditing against this synthetic store only.
func TestCreateAtomicallyStoresUserAndAudit(t *testing.T) {
	store := NewMemoryStore()
	input := Input{Username: "synthetic_user", Email: "synthetic@example.test", Age: 20, Consent: true}
	created, err := Create(context.Background(), store, input)
	if err != nil {
		t.Fatal(err)
	}
	users, audits := store.Snapshot()
	if len(users) != 1 || users[0] != created {
		t.Fatalf("users = %#v, created = %#v", users, created)
	}
	if len(audits) != 1 || audits[0].UserID != created.ID || audits[0].Action != "account.registered" {
		t.Fatalf("audits = %#v", audits)
	}
	if created.Email != "synthetic@example.test" {
		t.Fatalf("unexpected email: %q", created.Email)
	}
}

// Evidence basis: docs/roadmap/F18-F30-feature-approval.md, F25 (line 43)
// requires no real email or credentials; injected storage failure must leave no
// partial user or audit record.
func TestCreateRollsBackBothRecordsOnAuditFailure(t *testing.T) {
	store := NewMemoryStore()
	store.FailAudit = errors.New("synthetic audit failure")
	_, err := Create(context.Background(), store, Input{Username: "synthetic_user", Email: "synthetic@example.test", Age: 20, Consent: true})
	if err == nil {
		t.Fatal("expected synthetic audit failure")
	}
	users, audits := store.Snapshot()
	if len(users) != 0 || len(audits) != 0 {
		t.Fatalf("partial transaction: users=%#v audits=%#v", users, audits)
	}
}
