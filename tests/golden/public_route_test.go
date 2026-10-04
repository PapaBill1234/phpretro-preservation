package golden

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

const acceptedPublicRootCaptureHash = "59f4ec34d6f77b0cdabdf589e6e1d92fc1bd336fceeaad7cf5f48bdad288a6f7"

func syntheticPublicRootResponse() Response {
	body := "synthetic public root response"
	hash := sha256.Sum256([]byte(body))
	return Response{
		Method:       "GET", // synthetic fixture value, not measured capture metadata.
		Status:       200,   // synthetic fixture value, not measured capture metadata.
		Headers:      map[string]string{"content-type": "text/plain"},
		Body:         body,
		BodyMarkers:  []string{"synthetic public root"},
		ExpectedHash: hex.EncodeToString(hash[:]),
	}
}

func TestSyntheticPublicRootUsesComparator(t *testing.T) {
	// This provenance value is deliberately not used as the synthetic body hash.
	if acceptedPublicRootCaptureHash == "" {
		t.Fatal("accepted capture hash provenance must remain recorded")
	}

	expected := syntheticPublicRootResponse()
	if err := Compare(expected, expected); err != nil {
		t.Fatalf("synthetic fixture should compare equal: %v", err)
	}
}

func TestSyntheticPublicRootRejectsBodyMismatch(t *testing.T) {
	expected := syntheticPublicRootResponse()
	actual := expected
	actual.Body = "synthetic public root response changed"

	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected synthetic body hash mismatch")
	}
}
