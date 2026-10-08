package audit

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"reflect"
	"sort"
	"strings"
	"testing"
)

// Evidence basis: docs/roadmap/F31-F45-candidate-design.md, F35 row (line 53).
// The row requires a website-owned mutation plus audit record to commit
// atomically, negative cases for unauthorized/invalid/audit-failure, and
// prepared SQL. Schema, actor fields and the transaction boundary are UNKNOWN
// until the owner/security/schema gate closes, so these are synthetic fixtures.

func syntheticSelection() Selection {
	return SyntheticSelection
}

func validMutation() Mutation {
	return Mutation{Target: "synthetic.website_mutation", TargetID: "row-1", Value: "synthetic-value"}
}

// TestPrepareRejectsIncompleteSelection proves the coordinator selection
// (mutation, schema, actor fields, transaction boundary) must be recorded
// before dispatch, per F35 acceptance "recorded before dispatch".
func TestPrepareRejectsIncompleteSelection(t *testing.T) {
	cases := []Selection{
		{},
		{Mutation: "m", Schema: "s", TransactionBoundary: "t", RequiredRole: "r"}, // no actor fields
		{Mutation: "m", Schema: "s", ActorFields: []string{""}, TransactionBoundary: "t", RequiredRole: "r"},
		{Mutation: "m", Schema: "", ActorFields: []string{"a"}, TransactionBoundary: "t", RequiredRole: "r"},
		{Mutation: "m", Schema: "s", ActorFields: []string{"a"}, TransactionBoundary: "", RequiredRole: "r"},
		{Mutation: "m", Schema: "s", ActorFields: []string{"a"}, TransactionBoundary: "t", RequiredRole: ""},
	}
	for i, sel := range cases {
		if _, err := Prepare(sel); !errors.Is(err, ErrSelectionUnset) {
			t.Errorf("case %d: Prepare err = %v, want ErrSelectionUnset", i, err)
		}
	}
	if _, err := Prepare(syntheticSelection()); err != nil {
		t.Fatalf("valid selection rejected: %v", err)
	}
}

// TestPlanRecordsSelectionBeforeDispatch verifies the recorded boundary carries
// the selected mutation, schema, actor fields and boundary into the plan.
func TestPlanRecordsSelectionBeforeDispatch(t *testing.T) {
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	record := plan.Record()
	for _, want := range []string{
		syntheticSelection().Mutation,
		syntheticSelection().Schema,
		syntheticSelection().TransactionBoundary,
		"actor_id",
		"actor_role",
	} {
		if !strings.Contains(record, want) {
			t.Errorf("record %q missing %q", record, want)
		}
	}
}

// TestAuthorizedMutationCommitsAtomically covers the first F35 acceptance:
// an authorized valid mutation and its audit record commit together.
func TestAuthorizedMutationCommitsAtomically(t *testing.T) {
	store := NewMemoryStore()
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	if err := plan.Dispatch(context.Background(), store, actor, validMutation()); err != nil {
		t.Fatalf("dispatch: %v", err)
	}
	rows, audit := store.Snapshot()
	if len(rows) != 1 || rows[0].TargetID != "row-1" || rows[0].Value != "synthetic-value" {
		t.Fatalf("rows = %#v", rows)
	}
	if len(audit) != 1 {
		t.Fatalf("audit = %#v", audit)
	}
	want := AuditRecord{
		ActorID: "staff-1", ActorRole: syntheticSelection().RequiredRole,
		Action: syntheticSelection().Mutation, Target: "synthetic.website_mutation", TargetID: "row-1",
	}
	if audit[0] != want {
		t.Fatalf("audit = %#v, want %#v", audit[0], want)
	}
}

// TestReplayIsRejected proves a committed synthetic target cannot be applied
// twice. Evidence: docs/evidence/F35-audit-transaction.md, replay requirement.
func TestReplayIsRejected(t *testing.T) {
	store := NewMemoryStore()
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	if err := plan.Dispatch(context.Background(), store, actor, validMutation()); err != nil {
		t.Fatal(err)
	}
	if err := plan.Dispatch(context.Background(), store, actor, validMutation()); !errors.Is(err, ErrReplay) {
		t.Fatalf("replay err = %v, want ErrReplay", err)
	}
	rows, audit := store.Snapshot()
	if len(rows) != 1 || len(audit) != 1 {
		t.Fatalf("replay changed store: rows=%#v audit=%#v", rows, audit)
	}
}

// TestUnauthorizedOrInvalidCausesNoWriteNoAudit covers the second F35
// acceptance: denial happens before the store is touched.
func TestUnauthorizedOrInvalidCausesNoWriteNoAudit(t *testing.T) {
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		name  string
		actor Actor
		in    Mutation
		want  error
	}{
		{"wrong role", Actor{ID: "staff-1", Role: "guest"}, validMutation(), ErrUnauthorized},
		{"missing actor", Actor{Role: syntheticSelection().RequiredRole}, validMutation(), ErrUnauthorized},
		{"empty target id", Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}, Mutation{Target: "t", Value: "v"}, ErrInvalidInput},
		{"empty value", Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}, Mutation{Target: "t", TargetID: "row-1"}, ErrInvalidInput},
		{"control char", Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}, Mutation{Target: "t", TargetID: "row-1", Value: "a\nb"}, ErrInvalidInput},
	}
	for _, tc := range cases {
		store := NewMemoryStore()
		if err := plan.Dispatch(context.Background(), store, tc.actor, tc.in); !errors.Is(err, tc.want) {
			t.Errorf("%s: err = %v, want %v", tc.name, err, tc.want)
		}
		rows, audit := store.Snapshot()
		if len(rows) != 0 || len(audit) != 0 {
			t.Errorf("%s: wrote rows=%#v audit=%#v", tc.name, rows, audit)
		}
	}
}

// TestInjectedAuditFailureRollsBackMutation covers the third F35 acceptance:
// an audit failure leaves no partial mutation and no audit row.
func TestInjectedAuditFailureRollsBackMutation(t *testing.T) {
	store := NewMemoryStore()
	store.FailAudit = errors.New("synthetic audit failure")
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	err = plan.Dispatch(context.Background(), store, actor, validMutation())
	if !errors.Is(err, ErrAuditFailure) {
		t.Fatalf("err = %v, want ErrAuditFailure", err)
	}
	rows, audit := store.Snapshot()
	if len(rows) != 0 || len(audit) != 0 {
		t.Fatalf("partial commit: rows=%#v audit=%#v", rows, audit)
	}
}

// TestWriteFailureRollsBackAudit is the inverse half of the atomicity claim.
func TestWriteFailureRollsBackAudit(t *testing.T) {
	store := NewMemoryStore()
	store.FailWrite = errors.New("synthetic write failure")
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	if err := plan.Dispatch(context.Background(), store, actor, validMutation()); err == nil {
		t.Fatal("expected write failure")
	}
	rows, audit := store.Snapshot()
	if len(rows) != 0 || len(audit) != 0 {
		t.Fatalf("partial commit: rows=%#v audit=%#v", rows, audit)
	}
}

// TestDispatchRejectsNilStore ensures a missing store fails closed.
func TestDispatchRejectsNilStore(t *testing.T) {
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	if err := plan.Dispatch(context.Background(), nil, actor, validMutation()); !errors.Is(err, ErrStore) {
		t.Fatalf("err = %v, want ErrStore", err)
	}
}

// --- SQL-backed synthetic store (prepared/bound SQL, transaction) ----------

type fakeConn struct {
	begins       int
	rolled       bool
	committed    bool
	prepared     []string
	boundArgs    [][]driver.Value
	failAudit    bool
	zeroUpdate   bool
	stagedRows   map[string]string
	stagedAudit  []AuditRecord
	committedRow map[string]string
	committedAud []AuditRecord
}

type fakeDriver struct{ c *fakeConn }
type fakeTx struct{ c *fakeConn }

func (d fakeDriver) Open(string) (driver.Conn, error) { return d.c, nil }

func (c *fakeConn) Prepare(query string) (driver.Stmt, error) {
	c.prepared = append(c.prepared, query)
	return &fakeStmt{c: c, query: query}, nil
}
func (c *fakeConn) Close() error              { return nil }
func (c *fakeConn) Begin() (driver.Tx, error) { c.begins++; return &fakeTx{c: c}, nil }

func (t *fakeTx) Commit() error {
	for k, v := range t.c.stagedRows {
		if t.c.committedRow == nil {
			t.c.committedRow = map[string]string{}
		}
		t.c.committedRow[k] = v
	}
	t.c.committedAud = append(t.c.committedAud, t.c.stagedAudit...)
	t.c.committed = true
	return nil
}
func (t *fakeTx) Rollback() error {
	t.c.rolled = true
	t.c.stagedRows = nil
	t.c.stagedAudit = nil
	return nil
}

type fakeStmt struct {
	c     *fakeConn
	query string
}

func (s *fakeStmt) Close() error  { return nil }
func (s *fakeStmt) NumInput() int { return -1 }
func (s *fakeStmt) Query([]driver.Value) (driver.Rows, error) {
	return nil, errors.New("query not used")
}
func (s *fakeStmt) Exec(args []driver.Value) (driver.Result, error) {
	s.c.boundArgs = append(s.c.boundArgs, append([]driver.Value(nil), args...))
	switch {
	case strings.Contains(s.query, "INSERT INTO"):
		if s.c.failAudit {
			return nil, errors.New("synthetic audit insert failure")
		}
		s.c.stagedAudit = append(s.c.stagedAudit, AuditRecord{
			ActorID: str(args[0]), ActorRole: str(args[1]), Action: str(args[2]),
			Target: str(args[3]), TargetID: str(args[4]),
		})
	case strings.Contains(s.query, "UPDATE"):
		if s.c.zeroUpdate {
			return driver.RowsAffected(0), nil
		}
		if s.c.stagedRows == nil {
			s.c.stagedRows = map[string]string{}
		}
		s.c.stagedRows[str(args[1])] = str(args[0])
	default:
		return nil, errors.New("unexpected statement")
	}
	return driver.RowsAffected(1), nil
}

func str(v driver.Value) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func openFake(t *testing.T) (*fakeConn, *SQLStore) {
	t.Helper()
	c := &fakeConn{}
	name := "audit-fixture-" + strings.ReplaceAll(t.Name(), "/", "-")
	sql.Register(name, fakeDriver{c: c})
	db, err := sql.Open(name, "")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return c, NewSQLStore(db)
}

// TestSQLStoreUsesPreparedBoundTransaction covers the fourth F35 acceptance:
// prepared/bound SQL and a real transaction boundary, no string-built SQL.
func TestSQLStoreUsesPreparedBoundTransaction(t *testing.T) {
	c, store := openFake(t)
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	if err := plan.Dispatch(context.Background(), store, actor, validMutation()); err != nil {
		t.Fatalf("dispatch: %v", err)
	}
	if c.begins != 1 {
		t.Fatalf("transactions = %d, want 1", c.begins)
	}
	if !c.committed || c.rolled {
		t.Fatalf("committed=%v rolled=%v", c.committed, c.rolled)
	}
	if len(c.prepared) != 2 {
		t.Fatalf("prepared statements = %#v", c.prepared)
	}
	var placeholders int
	for _, q := range c.prepared {
		if !strings.Contains(q, "?") {
			t.Errorf("statement not parameterized: %q", q)
		}
		placeholders += strings.Count(q, "?")
	}
	if placeholders != 7 {
		t.Errorf("placeholders = %d, want 7", placeholders)
	}
	wantArgs := []driver.Value{"synthetic-value", "row-1"}
	if !reflect.DeepEqual(c.boundArgs[0], wantArgs) {
		t.Fatalf("mutation args = %#v, want %#v", c.boundArgs[0], wantArgs)
	}
	if len(c.committedAud) != 1 || c.committedAud[0].ActorID != "staff-1" {
		t.Fatalf("committed audit = %#v", c.committedAud)
	}
}

// TestSQLStoreAuditFailureRollsBack proves the injected audit failure leaves no
// committed mutation and no committed audit row in the transactional store.
func TestSQLStoreAuditFailureRollsBack(t *testing.T) {
	c, store := openFake(t)
	c.failAudit = true
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	actor := Actor{ID: "staff-1", Role: syntheticSelection().RequiredRole}
	if err := plan.Dispatch(context.Background(), store, actor, validMutation()); !errors.Is(err, ErrAuditFailure) {
		t.Fatalf("err = %v, want ErrAuditFailure", err)
	}
	if !c.rolled {
		t.Fatal("expected rollback")
	}
	if c.committed || len(c.committedRow) != 0 || len(c.committedAud) != 0 {
		t.Fatalf("partial commit: committed=%v rows=%#v audit=%#v", c.committed, c.committedRow, c.committedAud)
	}
}

// TestSQLStoreNilDatabase fails closed when no synthetic database is injected.
func TestSQLStoreNilDatabase(t *testing.T) {
	_, store := openFake(t)
	_ = store
	if err := NewSQLStore(nil).ApplyAtomically(context.Background(), validMutation(), AuditRecord{}); !errors.Is(err, ErrStore) {
		t.Fatalf("err = %v, want ErrStore", err)
	}
}

// TestSQLStoreRejectsInvalidMutationBeforeTransaction keeps invalid input out
// of the database entirely.
func TestSQLStoreRejectsInvalidMutationBeforeTransaction(t *testing.T) {
	c, store := openFake(t)
	if err := store.ApplyAtomically(context.Background(), Mutation{}, AuditRecord{}); !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("err = %v, want ErrInvalidInput", err)
	}
	if c.begins != 0 {
		t.Fatalf("transactions started for invalid input: %d", c.begins)
	}
}

// TestCanonicalRecordIsStable documents the recorded order for the evidence file.
func TestCanonicalRecordIsStable(t *testing.T) {
	plan, err := Prepare(syntheticSelection())
	if err != nil {
		t.Fatal(err)
	}
	fields := append([]string(nil), plan.Selection.ActorFields...)
	sort.Strings(fields)
	if !reflect.DeepEqual(fields, []string{"actor_id", "actor_role"}) {
		t.Fatalf("actor fields = %#v", fields)
	}
	if plan.Selection.TransactionBoundary == "" {
		t.Fatal("transaction boundary not recorded")
	}
}
