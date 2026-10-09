package audit_test

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"reflect"
	"strings"
	"testing"

	"github.com/PapaBill1234/phpretro-preservation/internal/audit"
)

type redactionFixtures struct {
	Successes []struct {
		Name     string
		Actor    audit.Actor
		Mutation audit.Mutation
		Expected audit.AuditRecord
	}
	UnsafeIdentifiers []struct{ Name, Value string } `json:"unsafe_identifiers"`
	SafeIdentifiers   []string                       `json:"safe_identifiers"`
}

func loadRedactionFixtures(t *testing.T) redactionFixtures {
	t.Helper()
	data, err := os.ReadFile("testdata/redaction_fixtures.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixtures redactionFixtures
	if err := json.Unmarshal(data, &fixtures); err != nil {
		t.Fatal(err)
	}
	if len(fixtures.Successes) == 0 || len(fixtures.UnsafeIdentifiers) == 0 || len(fixtures.SafeIdentifiers) == 0 {
		t.Fatal("redaction fixtures must not be empty")
	}
	return fixtures
}

// This observer delegates all writes and snapshots to the real disposable store.
type redactionStoreObserver struct {
	*audit.MemoryStore
	calls int
}

func (s *redactionStoreObserver) ApplyAtomically(ctx context.Context, m audit.Mutation, r audit.AuditRecord) error {
	s.calls++
	return s.MemoryStore.ApplyAtomically(ctx, m, r)
}
func redactionPlan(t *testing.T, selection audit.Selection) audit.Plan {
	t.Helper()
	p, err := audit.Prepare(selection)
	if err != nil {
		t.Fatal(err)
	}
	return p
}
func assertRedactionEmpty(t *testing.T, store *audit.MemoryStore) {
	t.Helper()
	rows, records := store.Snapshot()
	if len(rows) != 0 || len(records) != 0 {
		t.Fatalf("partial commit: rows=%v audits=%v", rows, records)
	}
}

// Evidence: docs/evidence/F39-a-audit-redaction.md (five fields; never mutation Value).
func TestRedactionExternalCommittedAllowList(t *testing.T) {
	for _, fixture := range loadRedactionFixtures(t).Successes {
		t.Run(fixture.Name, func(t *testing.T) {
			store := audit.NewMemoryStore()
			if err := redactionPlan(t, audit.SyntheticSelection).Dispatch(context.Background(), store, fixture.Actor, fixture.Mutation); err != nil {
				t.Fatal(err)
			}
			rows, records := store.Snapshot()
			if len(rows) != 1 || rows[0] != (audit.Row{Target: fixture.Mutation.Target, TargetID: fixture.Mutation.TargetID, Value: fixture.Mutation.Value}) {
				t.Fatalf("mutation not committed intact: %v", rows)
			}
			if len(records) != 1 || records[0] != fixture.Expected {
				t.Fatalf("allow-listed record mismatch: %v", records)
			}
			data, err := json.Marshal(records[0])
			if err != nil {
				t.Fatal(err)
			}
			var fields map[string]string
			if err := json.Unmarshal(data, &fields); err != nil {
				t.Fatal(err)
			}
			expected := map[string]string{"ActorID": fixture.Expected.ActorID, "ActorRole": fixture.Expected.ActorRole, "Action": fixture.Expected.Action, "Target": fixture.Expected.Target, "TargetID": fixture.Expected.TargetID}
			if !reflect.DeepEqual(fields, expected) {
				t.Fatalf("audit must contain exactly five allowed fields: %s", data)
			}
			if strings.Contains(string(data), fixture.Mutation.Value) {
				t.Fatalf("mutation Value leaked into audit: %s", data)
			}
		})
	}
}

func setRedactionField(r *audit.AuditRecord, field, value string) {
	switch field {
	case "ActorID":
		r.ActorID = value
	case "ActorRole":
		r.ActorRole = value
	case "Action":
		r.Action = value
	case "Target":
		r.Target = value
	case "TargetID":
		r.TargetID = value
	}
}

// Evidence: docs/evidence/F39-a-audit-redaction.md (identifier grammar and pre-store rejection).
func TestRedactionExternalUnsafeIdentifiers(t *testing.T) {
	fixtures := loadRedactionFixtures(t)
	base := fixtures.Successes[0]
	for _, field := range []string{"ActorID", "ActorRole", "Action", "Target", "TargetID"} {
		for _, unsafe := range fixtures.UnsafeIdentifiers {
			t.Run(field+"/"+unsafe.Name, func(t *testing.T) {
				record := base.Expected
				setRedactionField(&record, field, unsafe.Value)
				got, err := audit.RedactRecord(record)
				if !errors.Is(err, audit.ErrRedaction) || got != (audit.AuditRecord{}) {
					t.Fatalf("unsafe record not rejected: record=%v err=%v", got, err)
				}
				actor, mutation, selection := base.Actor, base.Mutation, audit.SyntheticSelection
				switch field {
				case "ActorID":
					actor.ID = unsafe.Value
				case "ActorRole":
					actor.Role = unsafe.Value
					selection.RequiredRole = unsafe.Value
				case "Action":
					selection.Mutation = unsafe.Value
				case "Target":
					mutation.Target = unsafe.Value
				case "TargetID":
					mutation.TargetID = unsafe.Value
				}
				store := &redactionStoreObserver{MemoryStore: audit.NewMemoryStore()}
				plan, prepErr := audit.Prepare(selection)
				if prepErr != nil {
					if unsafe.Value != "" || (field != "ActorRole" && field != "Action") || !errors.Is(prepErr, audit.ErrSelectionUnset) {
						t.Fatalf("unexpected preparation error: %v", prepErr)
					}
				} else {
					want := audit.ErrRedaction
					if unsafe.Value == "" {
						if field == "ActorID" {
							want = audit.ErrUnauthorized
						} else {
							want = audit.ErrInvalidInput
						}
					}
					if err := plan.Dispatch(context.Background(), store, actor, mutation); !errors.Is(err, want) {
						t.Fatalf("unsafe dispatch: got %v want %v", err, want)
					}
				}
				if store.calls != 0 {
					t.Fatalf("unsafe identifier reached injected store %d times", store.calls)
				}
				assertRedactionEmpty(t, store.MemoryStore)
				if err := store.MemoryStore.ApplyAtomically(context.Background(), base.Mutation, record); !errors.Is(err, audit.ErrRedaction) {
					t.Fatalf("direct store accepted unsafe audit: %v", err)
				}
				assertRedactionEmpty(t, store.MemoryStore)
			})
		}
	}
}

// Evidence: docs/evidence/F39-a-audit-redaction.md (1-64 ASCII identifier allow-list).
func TestRedactionExternalSafeBoundaries(t *testing.T) {
	fixtures := loadRedactionFixtures(t)
	for _, value := range fixtures.SafeIdentifiers {
		for _, field := range []string{"ActorID", "ActorRole", "Action", "Target", "TargetID"} {
			t.Run(field+"/"+value, func(t *testing.T) {
				expected := fixtures.Successes[0].Expected
				setRedactionField(&expected, field, value)
				got, err := audit.RedactRecord(expected)
				if err != nil || got != expected {
					t.Fatalf("safe boundary changed or rejected: got=%v err=%v", got, err)
				}
			})
		}
	}
}

// Evidence: docs/evidence/F35-audit-transaction.md (authorization and atomic failure rollback).
func TestRedactionExternalAuthorizationAndFailures(t *testing.T) {
	base := loadRedactionFixtures(t).Successes[0]
	for _, name := range []string{"wrong_role", "missing_actor", "audit_failure", "mutation_failure"} {
		t.Run(name, func(t *testing.T) {
			store := &redactionStoreObserver{MemoryStore: audit.NewMemoryStore()}
			actor := base.Actor
			want, calls := audit.ErrUnauthorized, 0
			switch name {
			case "wrong_role":
				actor.Role = "visitor"
			case "missing_actor":
				actor.ID = ""
			case "audit_failure":
				store.FailAudit = errors.New("synthetic audit failure")
				want = audit.ErrAuditFailure
				calls = 1
			case "mutation_failure":
				store.FailWrite = errors.New("synthetic write failure")
				want = audit.ErrWriteFailure
				calls = 1
			}
			plan := redactionPlan(t, audit.SyntheticSelection)
			if err := plan.Dispatch(context.Background(), store, actor, base.Mutation); !errors.Is(err, want) {
				t.Fatalf("failure classification: got %v want %v", err, want)
			}
			if store.calls != calls {
				t.Fatalf("store calls: got %d want %d", store.calls, calls)
			}
			assertRedactionEmpty(t, store.MemoryStore)
			store.FailAudit, store.FailWrite = nil, nil
			if err := plan.Dispatch(context.Background(), store, base.Actor, base.Mutation); err != nil {
				t.Fatalf("failed dispatch left residual state: %v", err)
			}
			rows, records := store.Snapshot()
			if len(rows) != 1 || len(records) != 1 || records[0] != base.Expected {
				t.Fatalf("recovery must commit exactly one pair: rows=%v records=%v", rows, records)
			}
		})
	}
}
