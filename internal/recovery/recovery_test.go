package recovery

import (
	"context"
	"testing"
)

// Evidence: docs/roadmap/F18-F30-feature-approval.md, F26 line 44: account enumeration/email behavior;
// absence of a dynamic capture makes identical wording an explicit conservative guess.
func TestUnknownAndKnownAccountResponsesAreIdentical(t *testing.T) {
	id := fakeIdentity{}
	store := NewMemoryStore()
	mailer := &fakeMailer{}
	unknown, err := Request(context.Background(), id, mailer, store, "missing@example.test")
	if err != nil {
		t.Fatal(err)
	}
	id.found = true
	known, err := Request(context.Background(), id, mailer, store, "known@example.test")
	if err != nil {
		t.Fatal(err)
	}
	if unknown != known {
		t.Fatalf("responses differ: %#v vs %#v", unknown, known)
	}
	if mailer.count != 1 {
		t.Fatalf("sent %d messages", mailer.count)
	}
}

// Evidence: docs/roadmap/F18-F30-feature-approval.md, F26 line 44: reset-token contract is unknown;
// one-time consumption is a synthetic-store guess, tested only with synthetic identity and mail.
func TestResetTokenIsSingleUse(t *testing.T) {
	id := fakeIdentity{found: true}
	store := NewMemoryStore()
	mailer := &fakeMailer{}
	if _, err := Request(context.Background(), id, mailer, store, "person@example.test"); err != nil {
		t.Fatal(err)
	}
	if mailer.token == "" {
		t.Fatal("no synthetic token mailed")
	}
	first, err := Reset(context.Background(), store, mailer.token)
	if err != nil || !first {
		t.Fatalf("first reset = %v, %v", first, err)
	}
	second, err := Reset(context.Background(), store, mailer.token)
	if err != nil || second {
		t.Fatalf("second reset = %v, %v", second, err)
	}
}

type fakeIdentity struct{ found bool }

func (f fakeIdentity) Lookup(context.Context, string) (string, bool, error) {
	return "synthetic-user", f.found, nil
}

type fakeMailer struct {
	count int
	token string
}

func (f *fakeMailer) Send(_ context.Context, _ string, token string) error {
	f.count++
	f.token = token
	return nil
}
