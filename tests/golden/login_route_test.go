package golden

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

const acceptedLoginCaptureHash = "500ebc46334b0c56b7947ee11fc63ce906b6e92f060fced732f12afef258d46d"

func syntheticLoginResponse() Response {
	body := "synthetic login-habblet login-username login-password login-submit-button forgot-password account/submit"
	hash := sha256.Sum256([]byte(body))
	return Response{
		Method: "GET", // Synthetic fixture value, not captured metadata.
		Status: 200,   // Synthetic fixture value, not captured metadata.
		Headers: map[string]string{
			"content-type":  "text/html; charset=UTF-8",
			"cache-control": "no-store, no-cache, must-revalidate, post-check=0, pre-check=0",
		},
		Body: body,
		BodyMarkers: []string{
			"login-habblet",
			"login-username",
			"login-password",
			"login-submit-button",
			"forgot-password",
			"account/submit",
		},
		ExpectedHash: hex.EncodeToString(hash[:]),
	}
}

func TestSyntheticLoginUsesComparator(t *testing.T) {
	if acceptedLoginCaptureHash == "" {
		t.Fatal("accepted capture hash provenance must remain recorded")
	}

	expected := syntheticLoginResponse()
	if err := Compare(expected, expected); err != nil {
		t.Fatalf("synthetic fixture should compare equal: %v", err)
	}
}

func TestSyntheticLoginRejectsStatusMismatch(t *testing.T) {
	expected := syntheticLoginResponse()
	actual := expected
	actual.Status = 403

	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected status mismatch")
	}
}

func TestSyntheticLoginRejectsRedirectMismatch(t *testing.T) {
	expected := syntheticLoginResponse()
	actual := expected
	actual.Location = "/client"

	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected redirect mismatch")
	}
}

func TestSyntheticLoginRejectsSelectedHeaderMismatch(t *testing.T) {
	expected := syntheticLoginResponse()
	actual := expected
	actual.Headers = map[string]string{
		"content-type":  "text/html; charset=UTF-8",
		"cache-control": "public, max-age=60",
	}

	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected selected header mismatch")
	}
}

func TestSyntheticLoginRejectsMissingMarker(t *testing.T) {
	expected := syntheticLoginResponse()
	actual := expected
	actual.Body = "synthetic login-habblet login-username login-password forgot-password account/submit"

	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected missing marker")
	}
}

func TestSyntheticLoginRejectsSyntheticBodyHashMismatch(t *testing.T) {
	expected := syntheticLoginResponse()
	actual := expected
	actual.Body = "synthetic login response changed"

	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected synthetic body hash mismatch")
	}
}
