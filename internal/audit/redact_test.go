package audit

import "testing"

func TestRedactRecordAllowListAndRejectUnsafe(t *testing.T) {
	// Evidence: docs/evidence/F35-audit-transaction.md:11-14 leaves the concrete schema unknown; this is a synthetic allow-list.
	got, err := RedactRecord(AuditRecord{ActorID: "actor-7", ActorRole: "staff", Action: "rename", Target: "profile", TargetID: "p-9"})
	if err != nil {
		t.Fatal(err)
	}
	want := AuditRecord{ActorID: "actor-7", ActorRole: "staff", Action: "rename", Target: "profile", TargetID: "p-9"}
	if got != want {
		t.Fatalf("RedactRecord() = %#v, want %#v", got, want)
	}
	for name, rec := range map[string]AuditRecord{
		"secret":  {ActorID: "actor", ActorRole: "staff", Action: "token=secret", Target: "profile", TargetID: "p-9"},
		"control": {ActorID: "actor\n", ActorRole: "staff", Action: "rename", Target: "profile", TargetID: "p-9"},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := RedactRecord(rec); err == nil {
				t.Fatal("unsafe audit value accepted")
			}
		})
	}
}
