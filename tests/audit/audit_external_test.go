// Package audit_test exercises the F35 audit mutation boundary as an external
// consumer, independent of the package's internal fixtures.
//
// Evidence: docs/roadmap/F31-F45-candidate-design.md, F35 row (line 53) and
// docs/evidence/F35-audit-transaction.md. The gate is open, so this uses the
// exported synthetic selection only.
package audit_test

import (
	"context"
	"errors"
	"testing"

	"github.com/PapaBill1234/phpretro-preservation/internal/audit"
)

func TestExternalAuthorizedCommitIsAtomic(t *testing.T) {
	plan, err := audit.Prepare(audit.SyntheticSelection)
	if err != nil {
		t.Fatal(err)
	}
	store := audit.NewMemoryStore()
	actor := audit.Actor{ID: "staff-1", Role: audit.SyntheticSelection.RequiredRole}
	mutation := audit.Mutation{Target: "synthetic.website_mutation", TargetID: "row-1", Value: "v1"}
	if err := plan.Dispatch(context.Background(), store, actor, mutation); err != nil {
		t.Fatalf("dispatch: %v", err)
	}
	rows, auditRows := store.Snapshot()
	if len(rows) != 1 || len(auditRows) != 1 {
		t.Fatalf("rows=%#v audit=%#v", rows, auditRows)
	}
}

func TestExternalUnauthorizedIsDenied(t *testing.T) {
	plan, err := audit.Prepare(audit.SyntheticSelection)
	if err != nil {
		t.Fatal(err)
	}
	store := audit.NewMemoryStore()
	actor := audit.Actor{ID: "guest-1", Role: "guest"}
	mutation := audit.Mutation{Target: "t", TargetID: "row-1", Value: "v"}
	if err := plan.Dispatch(context.Background(), store, actor, mutation); !errors.Is(err, audit.ErrUnauthorized) {
		t.Fatalf("err = %v, want ErrUnauthorized", err)
	}
	rows, auditRows := store.Snapshot()
	if len(rows) != 0 || len(auditRows) != 0 {
		t.Fatalf("write on denial: rows=%#v audit=%#v", rows, auditRows)
	}
}
