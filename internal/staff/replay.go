package staff

import (
	"encoding/json"
	"errors"
	"os"
	"sync"
	"time"
)

var (
	ErrReplay     = errors.New("totp step already used")
	ErrStepWindow = errors.New("totp step outside allowed window")
)

type ReplayStore interface {
	Consume(string, int64, time.Time) error
}
type Replay struct {
	Store ReplayStore
	Step  time.Duration
	Skew  int64
}

func (r Replay) Accept(identity string, step int64, now time.Time) error {
	if identity == "" || r.Step <= 0 || r.Skew < 0 {
		return ErrStepWindow
	}
	current := now.Unix() / int64(r.Step/time.Second)
	if step < current-r.Skew || step > current+r.Skew {
		return ErrStepWindow
	}
	if err := r.Store.Consume(identity, step, now); err != nil {
		if errors.Is(err, ErrReplay) {
			return ErrReplay
		}
		return ErrStore
	}
	return nil
}

type fileStore struct {
	mu   sync.Mutex
	path string
	Used map[string]map[int64]bool
}

func OpenReplayStore(path string) (ReplayStore, error) {
	s := &fileStore{path: path, Used: map[string]map[int64]bool{}}
	b, err := os.ReadFile(path) // #nosec G304 -- synthetic caller-selected persistence path
	if err == nil {
		if err = json.Unmarshal(b, s); err != nil {
			return nil, ErrStore
		}
	}
	if err != nil && !os.IsNotExist(err) {
		return nil, ErrStore
	}
	s.path = path
	if s.Used == nil {
		s.Used = map[string]map[int64]bool{}
	}
	return s, nil
}
func (s *fileStore) Consume(id string, step int64, _ time.Time) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.Used[id] == nil {
		s.Used[id] = map[int64]bool{}
	}
	if s.Used[id][step] {
		return ErrReplay
	}
	s.Used[id][step] = true
	b, err := json.Marshal(s)
	if err != nil {
		return ErrStore
	}
	f, err := os.OpenFile(s.path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0600)
	if err != nil {
		return ErrStore
	}
	if _, err = f.Write(b); err == nil {
		err = f.Close()
	} else {
		_ = f.Close()
	}
	if err != nil {
		return ErrStore
	}
	return nil
}
