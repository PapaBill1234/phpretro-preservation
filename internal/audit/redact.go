package audit

import (
	"errors"
	"regexp"
	"strings"
	"unicode"
)

var ErrRedaction = errors.New("audit record redaction failed")
var safeAuditIdentifier = regexp.MustCompile(`^[A-Za-z0-9_.:-]{1,64}$`)

// RedactRecord returns only the synthetic allow-listed audit columns. Unsafe
// values are rejected rather than persisted; the concrete production schema
// remains behind the owner/security/schema gate.
func RedactRecord(in AuditRecord) (AuditRecord, error) {
	out := AuditRecord{ActorID: in.ActorID, ActorRole: in.ActorRole, Action: in.Action, Target: in.Target, TargetID: in.TargetID}
	for _, value := range []string{out.ActorID, out.ActorRole, out.Action, out.Target, out.TargetID} {
		lower := strings.ToLower(value)
		if !safeAuditIdentifier.MatchString(value) || strings.TrimSpace(value) == "" || strings.Contains(lower, "secret") || strings.Contains(lower, "token") || strings.Contains(lower, "password") || strings.HasPrefix(lower, "sk-") || strings.HasPrefix(lower, "bearer") {
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
