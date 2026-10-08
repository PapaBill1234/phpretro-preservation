package audit

import (
	"errors"
	"strings"
	"unicode"
)

var ErrRedaction = errors.New("audit record redaction failed")

// RedactRecord returns only the synthetic allow-listed audit columns. Unsafe
// values are rejected rather than persisted; the concrete production schema
// remains behind the owner/security/schema gate.
func RedactRecord(in AuditRecord) (AuditRecord, error) {
	out := AuditRecord{ActorID: in.ActorID, ActorRole: in.ActorRole, Action: in.Action, Target: in.Target, TargetID: in.TargetID}
	for _, value := range []string{out.ActorID, out.ActorRole, out.Action, out.Target, out.TargetID} {
		if strings.TrimSpace(value) == "" || strings.Contains(value, "=") || strings.Contains(strings.ToLower(value), "secret") || strings.Contains(strings.ToLower(value), "token") {
			return AuditRecord{}, ErrRedaction
		}
		for _, r := range value {
			if unicode.IsControl(r) {
				return AuditRecord{}, ErrRedaction
			}
		}
	}
	return out, nil
}
