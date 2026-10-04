package golden

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

const (
	acceptedArchiveBodyHash   = "4086e3ddfe758ecb82f90a3dc6c46c9fbdb1c51ddcee5d513d970ea5e31f9886"
	acceptedArchiveHeaderHash = "a935af6c45f2c58111589e3a47f141eb2cfd436b2ee70acba193e7e9b1ae541d"
)

func syntheticArchiveResponse() Response {
	body := `<div id="article-archive"><div id="article-paging"></div><div id="article-wrapper"></div></div>`
	hash := sha256.Sum256([]byte(body))
	return Response{
		Method:   "GET",
		Status:   200,
		Location: "",
		Cookies:  []string{},
		Headers: map[string]string{
			"content-type":  "text/html; charset=UTF-8",
			"cache-control": "no-store, no-cache, must-revalidate, post-check=0, pre-check=0",
		},
		Body: body,
		BodyMarkers: []string{
			"article-archive",
			"article-paging",
			"article-wrapper",
		},
		ExpectedHash: hex.EncodeToString(hash[:]),
	}
}

func TestSyntheticArchiveAcceptsObservedContract(t *testing.T) {
	// Capture hashes are provenance and intentionally differ from this fixture hash.
	if acceptedArchiveBodyHash == "" || acceptedArchiveHeaderHash == "" {
		t.Fatal("capture provenance must remain recorded")
	}

	expected := syntheticArchiveResponse()
	if expected.ExpectedHash == acceptedArchiveBodyHash {
		t.Fatal("synthetic fixture must not reuse the capture body hash")
	}
	if err := Compare(expected, expected); err != nil {
		t.Fatalf("synthetic archive fixture should compare equal: %v", err)
	}
}

func TestSyntheticArchiveRejectsMethodMismatch(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Method = "POST"
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func TestSyntheticArchiveRejectsStatusMismatch(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Status = 500
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func TestSyntheticArchiveRejectsLocationMismatch(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Location = "/login"
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func TestSyntheticArchiveRejectsSelectedHeaderMismatch(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Headers = cloneHeaders(expected.Headers)
	actual.Headers["cache-control"] = "public"
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func TestSyntheticArchiveRejectsCookieMismatch(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Cookies = []string{"PHPSESSID=unexpected"}
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func TestSyntheticArchiveRejectsMissingMarker(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Body = `<div id="article-paging"></div><div id="article-wrapper"></div>`
	actual.ExpectedHash = ""
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func TestSyntheticArchiveRejectsBodyHashMismatch(t *testing.T) {
	expected := syntheticArchiveResponse()
	actual := expected
	actual.Body = actual.Body + " changed"
	assertSyntheticArchiveMismatch(t, expected, actual)
}

func assertSyntheticArchiveMismatch(t *testing.T, expected, actual Response) {
	t.Helper()
	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected synthetic archive mismatch")
	}
}

func cloneHeaders(headers map[string]string) map[string]string {
	clone := make(map[string]string, len(headers))
	for key, value := range headers {
		clone[key] = value
	}
	return clone
}
