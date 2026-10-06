package staff

import "fmt"

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 requires durable atomic
// compare/update of a staff identity and time-step pair.
type ReplayStore interface {
	CompareAndStore(identity string, step int64) (accepted bool, err error)
}

type ReplayStoreGuard struct{ store ReplayStore }

// NewReplayStore creates a replay guard over an injected durable store.
func NewReplayStore(store ReplayStore) *ReplayStoreGuard { return &ReplayStoreGuard{store: store} }

// Accept returns true only when the pair has not previously been recorded.
// Store errors fail closed: no acceptance is reported alongside an error.
func (r *ReplayStoreGuard) Accept(identity string, step int64) (bool, error) {
	if r == nil || r.store == nil || identity == "" {
		return false, fmt.Errorf("invalid replay store or identity")
	}
	accepted, err := r.store.CompareAndStore(identity, step)
	if err != nil {
		return false, err
	}
	return accepted, nil
}
