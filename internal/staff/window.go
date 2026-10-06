package staff

import (
	"sync"
	"time"
)

// The ±1-step allowance, 30-second interval, and expiry semantics are guessed
// pending the owner/security/schema gate documented in F31-F45-candidate-design.md.
const guessedStepWindow = int64(1)

// StepWindow tracks synthetic accepted staff/time-step pairs in memory. It is
// not a durable production replay store.
type StepWindow struct {
	mu       sync.Mutex
	accepted map[stepKey]struct{}
}

type stepKey struct {
	staffID string
	step    int64
}

// NewStepWindow creates an empty synthetic replay window.
func NewStepWindow() *StepWindow {
	return &StepWindow{accepted: make(map[stepKey]struct{})}
}

// Accept admits a step within one interval of the current 30-second step and
// strictly before expiresAt. Each staff/step pair is accepted at most once.
func (w *StepWindow) Accept(staffID string, step int64, now, expiresAt time.Time) bool {
	if w == nil || staffID == "" || !now.Before(expiresAt) {
		return false
	}
	current := now.Unix() / 30
	if step < current-guessedStepWindow || step > current+guessedStepWindow {
		return false
	}
	w.mu.Lock()
	defer w.mu.Unlock()
	key := stepKey{staffID: staffID, step: step}
	if _, exists := w.accepted[key]; exists {
		return false
	}
	w.accepted[key] = struct{}{}
	return true
}
