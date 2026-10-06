package staff

import (
	"testing"
	"time"
)

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 names adjacent-step
// acceptance and replay rejection; the one-step skew is an explicit guess.
func TestWindowAcceptsAdjacentStepOnce(t *testing.T) {
	window := NewStepWindow()
	now := time.Unix(300, 0) // step 10 under the guessed 30-second period
	if !window.Accept("staff-1", 9, now, now.Add(time.Minute)) {
		t.Fatal("first adjacent step was rejected")
	}
	if window.Accept("staff-1", 9, now, now.Add(time.Minute)) {
		t.Fatal("duplicate lower adjacent step was accepted")
	}
	if !window.Accept("staff-1", 11, now, now.Add(time.Minute)) {
		t.Fatal("upper adjacent step was rejected")
	}
	if window.Accept("staff-1", 11, now, now.Add(time.Minute)) {
		t.Fatal("duplicate upper adjacent step was accepted")
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 requires rejection
// outside the approved window; ±1 step is an explicit guessed policy.
func TestWindowRejectsStepOutsideApprovedWindow(t *testing.T) {
	window := NewStepWindow()
	now := time.Unix(300, 0)
	if window.Accept("staff-1", 8, now, now.Add(time.Minute)) {
		t.Fatal("step two intervals behind was accepted")
	}
	if window.Accept("staff-1", 12, now, now.Add(time.Minute)) {
		t.Fatal("step two intervals ahead was accepted")
	}
}

// Evidence: docs/roadmap/F31-F45-candidate-design.md:56 calls for expiry
// coverage; expiration-at-or-after is an explicit guessed boundary.
func TestWindowExpiryBoundary(t *testing.T) {
	window := NewStepWindow()
	expires := time.Unix(330, 0)
	if !window.Accept("staff-1", 11, expires.Add(-time.Nanosecond), expires) {
		t.Fatal("last valid instant was rejected")
	}
	if window.Accept("staff-2", 11, expires, expires) {
		t.Fatal("first invalid instant was accepted")
	}
}
