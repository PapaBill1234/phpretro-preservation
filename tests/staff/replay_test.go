package staff_test

import (
	"errors"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/staff"
)

// Evidence basis: docs/roadmap/F31-F45-candidate-design.md, F38 row. The
// fixture identifies duplicate-step, race, adjacent-step, expiry, wrong-staff,
// outage, and durable-state tests as synthetic because the replay schema is
// unknown.
func TestReplayAcceptsOnceAndPersists(t *testing.T) {
	path := filepath.Join(t.TempDir(), "replay.json")
	store, err := staff.OpenReplayStore(path)
	if err != nil {
		t.Fatal(err)
	}
	r := staff.Replay{Store: store, Step: 30 * time.Second, Skew: 1}
	now := time.Unix(1000, 0).UTC()
	if err := r.Accept("staff-a", 33, now); err != nil {
		t.Fatal(err)
	}
	if !errors.Is(r.Accept("staff-a", 33, now), staff.ErrReplay) {
		t.Fatal("replay accepted")
	}
	store, err = staff.OpenReplayStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if !errors.Is((staff.Replay{Store: store, Step: 30 * time.Second, Skew: 1}).Accept("staff-a", 33, now), staff.ErrReplay) {
		t.Fatal("replay was not durable")
	}
}

// Evidence basis: docs/roadmap/F31-F45-candidate-design.md, F38 row.
func TestReplayConcurrentExactlyOne(t *testing.T) {
	store, err := staff.OpenReplayStore(filepath.Join(t.TempDir(), "replay.json"))
	if err != nil {
		t.Fatal(err)
	}
	r := staff.Replay{Store: store, Step: 30 * time.Second, Skew: 1}
	now := time.Unix(1000, 0).UTC()
	var wg sync.WaitGroup
	results := make(chan error, 20)
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); results <- r.Accept("staff-a", 33, now) }()
	}
	wg.Wait()
	successes := 0
	for i := 0; i < 20; i++ {
		if err := <-results; err == nil {
			successes++
		}
	}
	if successes != 1 {
		t.Fatalf("successes = %d, want 1", successes)
	}
}

// Evidence basis: docs/roadmap/F31-F45-candidate-design.md, F38 row.
func TestReplayWindowAndBoundary(t *testing.T) {
	store, _ := staff.OpenReplayStore(filepath.Join(t.TempDir(), "replay.json"))
	r := staff.Replay{Store: store, Step: 30 * time.Second, Skew: 1}
	if err := r.Accept("a", 32, time.Unix(1000, 0)); err != nil {
		t.Fatal(err)
	}
	if err := r.Accept("a", 35, time.Unix(1000, 0)); !errors.Is(err, staff.ErrStepWindow) {
		t.Fatal(err)
	}
	if err := r.Accept("b", 35, time.Unix(1000, 0)); !errors.Is(err, staff.ErrStepWindow) {
		t.Fatal(err)
	}
	if err := r.Accept("a", 33, time.Unix(1030, 0)); err != nil {
		t.Fatal(err)
	}
}

// Evidence basis: docs/roadmap/F31-F45-candidate-design.md, F38 row.
func TestReplayStoreOutageFailsClosed(t *testing.T) {
	r := staff.Replay{Store: failingStore{}, Step: 30 * time.Second, Skew: 1}
	if !errors.Is(r.Accept("a", 33, time.Unix(1000, 0)), staff.ErrStore) {
		t.Fatal("outage did not fail closed")
	}
}

type failingStore struct{}

func (failingStore) Consume(string, int64, time.Time) error { return errors.New("down") }
