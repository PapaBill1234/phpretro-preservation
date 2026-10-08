package audit

import (
	"context"
	"errors"
	"testing"
)

type recordingAuditStore struct{ calls int }

func (s *recordingAuditStore) ApplyAtomically(context.Context, Mutation, AuditRecord) error {
	s.calls++
	return nil
}

func TestDispatchRedactionFailurePreventsAnyStoreCall(t *testing.T) {
	// Evidence: docs/evidence/F39-a-audit-redaction.md; synthetic fail-closed contract.
	plan, err := Prepare(SyntheticSelection)
	if err != nil {
		t.Fatal(err)
	}
	for _, actorID := range []string{"actor\n", "sk-development-placeholder", "password-development", "Bearer-development"} {
		store := &recordingAuditStore{}
		err := plan.Dispatch(context.Background(), store, Actor{ID: actorID, Role: "staff"}, Mutation{Target: "profile", TargetID: "7", Value: "new value"})
		if !errors.Is(err, ErrRedaction) || store.calls != 0 {
			t.Fatalf("redaction failure touched store: err=%v calls=%d", err, store.calls)
		}
	}
}

func TestDirectStoresRejectUnsafeAuditRecordBeforeCommit(t *testing.T) {
	// Evidence: docs/evidence/F39-a-audit-redaction.md; injected stores remain synthetic.
	mutation := Mutation{Target: "profile", TargetID: "7", Value: "value"}
	record := AuditRecord{ActorID: "actor", ActorRole: "staff", Action: "token=development", Target: "profile", TargetID: "7"}
	memory := NewMemoryStore()
	if !errors.Is(memory.ApplyAtomically(context.Background(), mutation, record), ErrRedaction) {
		t.Fatal("direct memory store accepted unsafe audit")
	}
	rows, audits := memory.Snapshot()
	if len(rows) != 0 || len(audits) != 0 {
		t.Fatal("unsafe pair committed")
	}
	conn, sqlStore := openFake(t)
	if !errors.Is(sqlStore.ApplyAtomically(context.Background(), mutation, record), ErrRedaction) || conn.begins != 0 {
		t.Fatal("unsafe audit started SQL transaction")
	}
}

func TestAbsentMutationCannotCommitAudit(t *testing.T) {
	// Evidence: docs/evidence/F39-a-audit-redaction.md; exactly one synthetic
	// mutation must commit with its audit record, otherwise neither commits.
	conn, store := openFake(t)
	conn.zeroUpdate = true
	plan, _ := Prepare(SyntheticSelection)
	err := plan.Dispatch(context.Background(), store, Actor{ID: "actor", Role: "staff"}, Mutation{Target: "profile", TargetID: "7", Value: "value"})
	if !errors.Is(err, ErrWriteFailure) || conn.committed || !conn.rolled || len(conn.committedAud) != 0 {
		t.Fatalf("absent mutation committed audit: err=%v committed=%v rolled=%v", err, conn.committed, conn.rolled)
	}
}
