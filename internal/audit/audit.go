// Package audit implements a synthetic, website-owned mutation that commits
// atomically with its audit record.
//
// Fidelity: guessed. The coordinator/security/schema gate for F35 is open:
// the concrete mutation, audit schema, actor fields and transaction boundary
// are UNKNOWN (docs/roadmap/F31-F45-candidate-design.md, F35 row, line 53).
// This package therefore uses only synthetic selections and an injected,
// disposable store; it does not touch a production database or enable any
// real mutation. Independent security review is still required.
package audit

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"
)

var (
	ErrSelectionUnset = errors.New("audit selection unset")
	ErrUnauthorized   = errors.New("audit mutation unauthorized")
	ErrInvalidInput   = errors.New("audit mutation invalid")
	ErrAuditFailure   = errors.New("audit record failure")
	ErrReplay         = errors.New("audit mutation replay rejected")
	ErrWriteFailure   = errors.New("audit mutation write failure")
	ErrStore          = errors.New("audit store unavailable")
)

// Selection is the coordinator-recorded decision that must exist before any
// mutation dispatches: which mutation, which schema, which actor fields, and
// where the transaction boundary lies. Every value is UNKNOWN until the F35
// owner/security/schema gate closes, so the exported synthetic selection below
// is explicitly a placeholder.
type Selection struct {
	Mutation            string
	Schema              string
	ActorFields         []string
	TransactionBoundary string
	RequiredRole        string
}

// SyntheticSelection is a disposable placeholder used only by synthetic tests.
// It records the shape the coordinator must supply; it is not an approved
// mutation, schema, or actor-field decision.
var SyntheticSelection = Selection{
	Mutation:            "website.mutation.update",
	Schema:              "synthetic.website_schema",
	ActorFields:         []string{"actor_id", "actor_role"},
	TransactionBoundary: "single-transaction",
	RequiredRole:        "staff",
}

// Actor is the authenticated principal bound to the audit record.
type Actor struct {
	ID   string
	Role string
}

// Mutation is the website-owned change to apply. Target is a synthetic table
// label, never a production identifier.
type Mutation struct {
	Target   string
	TargetID string
	Value    string
}

// Row is a committed synthetic mutation row.
type Row struct {
	Target   string
	TargetID string
	Value    string
}

// AuditRecord is the redacted audit row written atomically with the mutation.
type AuditRecord struct {
	ActorID   string
	ActorRole string
	Action    string
	Target    string
	TargetID  string
}

// Store is the atomic mutation+audit boundary. ApplyAtomically must commit the
// mutation and its audit record together or neither.
type Store interface {
	ApplyAtomically(ctx context.Context, mutation Mutation, record AuditRecord) error
}

// Plan is a prepared, recorded dispatch. The selection is fixed before any
// store is touched.
type Plan struct {
	Selection Selection
}

// Prepare records the coordinator selection before dispatch. An incomplete
// selection is rejected so that no mutation dispatches without a recorded
// mutation, schema, actor fields and transaction boundary.
func Prepare(sel Selection) (Plan, error) {
	if err := sel.validate(); err != nil {
		return Plan{}, err
	}
	return Plan{Selection: sel}, nil
}

func (s Selection) validate() error {
	if strings.TrimSpace(s.Mutation) == "" || strings.TrimSpace(s.Schema) == "" ||
		strings.TrimSpace(s.TransactionBoundary) == "" || strings.TrimSpace(s.RequiredRole) == "" ||
		len(s.ActorFields) == 0 {
		return ErrSelectionUnset
	}
	for _, f := range s.ActorFields {
		if strings.TrimSpace(f) == "" {
			return ErrSelectionUnset
		}
	}
	return nil
}

// Record renders the recorded selection for evidence. Field order is sorted so
// the record is stable and comparable.
func (p Plan) Record() string {
	fields := append([]string(nil), p.Selection.ActorFields...)
	sort.Strings(fields)
	return fmt.Sprintf("mutation=%s schema=%s actor_fields=%s transaction_boundary=%s",
		p.Selection.Mutation, p.Selection.Schema, strings.Join(fields, ","), p.Selection.TransactionBoundary)
}

// Dispatch authorizes and validates the input, then delegates the atomic write
// to the store. Unauthorized or invalid input returns before the store is
// touched, so no write and no audit row can occur.
func (p Plan) Dispatch(ctx context.Context, store Store, actor Actor, mutation Mutation) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if strings.TrimSpace(actor.ID) == "" || actor.Role != p.Selection.RequiredRole {
		return ErrUnauthorized
	}
	if err := validateMutation(mutation); err != nil {
		return err
	}
	if store == nil {
		return ErrStore
	}
	record := AuditRecord{
		ActorID:   actor.ID,
		ActorRole: actor.Role,
		Action:    p.Selection.Mutation,
		Target:    mutation.Target,
		TargetID:  mutation.TargetID,
	}
	record, err := RedactRecord(record)
	if err != nil {
		return err
	}
	return store.ApplyAtomically(ctx, mutation, record)
}

func validateMutation(m Mutation) error {
	if strings.TrimSpace(m.Target) == "" || strings.TrimSpace(m.TargetID) == "" || m.Value == "" {
		return ErrInvalidInput
	}
	for _, r := range m.Value {
		if r == '\n' || r == '\r' || r == 0 {
			return ErrInvalidInput
		}
	}
	return nil
}

// MemoryStore is a synthetic atomic store. The lock makes the staged pair
// indivisible to readers, and every injected failure is checked before either
// record is staged, so a failure never yields a partial commit.
type MemoryStore struct {
	mu        sync.Mutex
	rows      []Row
	audit     []AuditRecord
	FailWrite error
	FailAudit error
}

func NewMemoryStore() *MemoryStore { return &MemoryStore{} }

func (s *MemoryStore) ApplyAtomically(ctx context.Context, mutation Mutation, record AuditRecord) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := validateMutation(mutation); err != nil {
		return err
	}
	var err error
	record, err = RedactRecord(record)
	if err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, row := range s.rows {
		if row.Target == mutation.Target && row.TargetID == mutation.TargetID {
			return ErrReplay
		}
	}
	if s.FailWrite != nil {
		return fmt.Errorf("%w: %v", ErrWriteFailure, s.FailWrite)
	}
	if s.FailAudit != nil {
		return fmt.Errorf("%w: %v", ErrAuditFailure, s.FailAudit)
	}
	s.rows = append(s.rows, Row(mutation))
	s.audit = append(s.audit, record)
	return nil
}

// Snapshot returns copies of the committed rows and audit records.
func (s *MemoryStore) Snapshot() ([]Row, []AuditRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]Row(nil), s.rows...), append([]AuditRecord(nil), s.audit...)
}

// SQL queries are fixed literals with placeholders; no value is ever
// interpolated into SQL text. The table names are the synthetic selection.
const (
	mutationSQL = "UPDATE synthetic.website_mutation SET value = ? WHERE id = ?"
	auditSQL    = "INSERT INTO synthetic.audit_log (actor_id, actor_role, action, target, target_id) VALUES (?, ?, ?, ?, ?)"
)

// SQLStore is a synthetic transactional store over an injected disposable
// *sql.DB. It uses prepared, bound statements inside one transaction; the
// caller supplies the handle, so no production store is touched by this unit.
type SQLStore struct{ db *sql.DB }

func NewSQLStore(db *sql.DB) *SQLStore { return &SQLStore{db: db} }

func (s *SQLStore) ApplyAtomically(ctx context.Context, mutation Mutation, record AuditRecord) error {
	if s == nil || s.db == nil {
		return ErrStore
	}
	if err := validateMutation(mutation); err != nil {
		return err
	}
	var redactionErr error
	record, redactionErr = RedactRecord(record)
	if redactionErr != nil {
		return redactionErr
	}
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrStore, err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()

	update, err := tx.PrepareContext(ctx, mutationSQL)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrWriteFailure, err)
	}
	defer update.Close()
	result, err := update.ExecContext(ctx, mutation.Value, mutation.TargetID)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrWriteFailure, err)
	}
	affected, err := result.RowsAffected()
	if err != nil || affected != 1 {
		return ErrWriteFailure
	}

	insert, err := tx.PrepareContext(ctx, auditSQL)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrAuditFailure, err)
	}
	defer insert.Close()
	if _, err := insert.ExecContext(ctx, record.ActorID, record.ActorRole, record.Action, record.Target, record.TargetID); err != nil {
		return fmt.Errorf("%w: %v", ErrAuditFailure, err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("%w: %v", ErrStore, err)
	}
	committed = true
	return nil
}
