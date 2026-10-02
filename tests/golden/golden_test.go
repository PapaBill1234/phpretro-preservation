package golden

import "testing"

func TestCompareSyntheticResponse(t *testing.T) {
	expected := Response{Method: "GET", Status: 200, Headers: map[string]string{"content-type": "text/html"}, Body: "synthetic-body", BodyMarkers: []string{"synthetic"}}
	expected.ExpectedHash = "" // fixture body is intentionally not a production capture.
	if err := Compare(expected, expected); err != nil {
		t.Fatal(err)
	}
}

func TestCompareRejectsMismatch(t *testing.T) {
	expected := Response{Method: "GET", Status: 200, Headers: map[string]string{}, BodyMarkers: []string{"required"}}
	actual := Response{Method: "GET", Status: 500, Headers: map[string]string{}, Body: "missing"}
	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected mismatch")
	}
}

func TestCompareRejectsHashMismatch(t *testing.T) {
	expected := Response{Method: "GET", Status: 200, Headers: map[string]string{}, ExpectedHash: "0000000000000000000000000000000000000000000000000000000000000000"}
	actual := Response{Method: "GET", Status: 200, Headers: map[string]string{}, Body: "synthetic"}
	if err := Compare(expected, actual); err == nil {
		t.Fatal("expected hash mismatch")
	}
}
