package staff

import (
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"testing"
)

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 requires atomic durable
// replay state keyed by staff identity and TOTP time step.
func TestReplayRejectsPreviouslyAcceptedStep(t *testing.T) {
	store := newFileReplayStore(t)
	replay := NewReplayStore(store)
	if ok, err := replay.Accept("staff-1", 42); err != nil || !ok {
		t.Fatalf("first accept = %v, %v", ok, err)
	}
	if ok, err := replay.Accept("staff-1", 42); err != nil || ok {
		t.Fatalf("replay accept = %v, %v", ok, err)
	}
	if ok, err := replay.Accept("staff-1", 43); err != nil || !ok {
		t.Fatalf("adjacent step = %v, %v", ok, err)
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 requires concurrent
// submissions of one step to admit exactly one success.
func TestReplayConcurrentSingleWinner(t *testing.T) {
	store := newFileReplayStore(t)
	replay := NewReplayStore(store)
	const attempts = 32
	results := make(chan bool, attempts)
	var wg sync.WaitGroup
	for i := 0; i < attempts; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); ok, err := replay.Accept("staff-1", 99); results <- err == nil && ok }()
	}
	wg.Wait()
	close(results)
	wins := 0
	for ok := range results {
		if ok {
			wins++
		}
	}
	if wins != 1 {
		t.Fatalf("wins = %d, want 1", wins)
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 requires outage/error
// handling to fail closed rather than accepting a replay step.
func TestReplayStoreErrorFailsClosed(t *testing.T) {
	replay := NewReplayStore(errorReplayStore{err: errors.New("store unavailable")})
	if ok, err := replay.Accept("staff-1", 1); ok || err == nil {
		t.Fatalf("accept = %v, %v", ok, err)
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 requires replay state
// to survive reopening the durable store.
func TestReplaySurvivesReopen(t *testing.T) {
	path := filepath.Join(t.TempDir(), "replay.db")
	first := openFileReplayStore(t, path)
	if ok, err := NewReplayStore(first).Accept("staff-1", 7); err != nil || !ok {
		t.Fatalf("first accept = %v, %v", ok, err)
	}
	second := openFileReplayStore(t, path)
	if ok, err := NewReplayStore(second).Accept("staff-1", 7); err != nil || ok {
		t.Fatalf("reopened replay = %v, %v", ok, err)
	}
}

type errorReplayStore struct{ err error }

func (s errorReplayStore) CompareAndStore(string, int64) (bool, error) { return false, s.err }

type fileReplayStore struct {
	mu      sync.Mutex
	path    string
	entries map[string]struct{}
}

func newFileReplayStore(t *testing.T) *fileReplayStore {
	return openFileReplayStore(t, filepath.Join(t.TempDir(), "replay.db"))
}
func openFileReplayStore(t *testing.T, path string) *fileReplayStore {
	s := &fileReplayStore{path: path, entries: map[string]struct{}{}}
	if data, err := os.ReadFile(path); err == nil {
		for _, line := range splitLines(data) {
			if len(line) == 0 {
				continue
			}
			sep := -1
			for i, b := range line {
				if b == '	' {
					sep = i
					break
				}
			}
			if sep < 0 {
				t.Fatalf("invalid replay entry %q", line)
			}
			identityBytes, err := hex.DecodeString(string(line[:sep]))
			if err != nil {
				t.Fatal(err)
			}
			step, err := strconv.ParseInt(string(line[sep+1:]), 10, 64)
			if err != nil {
				t.Fatal(err)
			}
			s.entries[replayKey(string(identityBytes), step)] = struct{}{}
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		t.Fatal(err)
	}
	return s
}
func (s *fileReplayStore) CompareAndStore(identity string, step int64) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := replayKey(identity, step)
	if _, exists := s.entries[key]; exists {
		return false, nil
	}
	entries := make(map[string]struct{}, len(s.entries)+1)
	for existing := range s.entries {
		entries[existing] = struct{}{}
	}
	entries[key] = struct{}{}
	var data []byte
	for entry := range entries {
		data = append(data, []byte(entry+"\n")...)
	}
	tmp := s.path + ".tmp"
	if err := os.WriteFile(tmp, data, 0600); err != nil {
		return false, err
	}
	if err := os.Rename(tmp, s.path); err != nil {
		_ = os.Remove(tmp)
		return false, err
	}
	s.entries = entries
	return true, nil
}
func splitLines(data []byte) [][]byte {
	var out [][]byte
	start := 0
	for i, b := range data {
		if b == '\n' {
			out = append(out, data[start:i])
			start = i + 1
		}
	}
	return out
}
func replayKey(identity string, step int64) string {
	return fmt.Sprintf("%x	%d", []byte(identity), step)
}
