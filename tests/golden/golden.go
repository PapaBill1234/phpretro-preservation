package golden

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

type Response struct {
	Method       string
	Status       int
	Location     string
	Cookies      []string
	Headers      map[string]string
	Body         string
	BodyMarkers  []string
	ExpectedHash string
}

func Compare(expected, actual Response) error {
	if expected.Method != actual.Method || expected.Status != actual.Status || expected.Location != actual.Location {
		return fmt.Errorf("method/status/redirect mismatch")
	}
	if strings.Join(expected.Cookies, "\n") != strings.Join(actual.Cookies, "\n") {
		return fmt.Errorf("cookie mismatch")
	}
	for key, value := range expected.Headers {
		if actual.Headers[key] != value {
			return fmt.Errorf("header %s mismatch", key)
		}
	}
	for _, marker := range expected.BodyMarkers {
		if !strings.Contains(actual.Body, marker) {
			return fmt.Errorf("body marker %q missing", marker)
		}
	}
	gotHash := sha256.Sum256([]byte(actual.Body))
	if expected.ExpectedHash != "" && hex.EncodeToString(gotHash[:]) != expected.ExpectedHash {
		return fmt.Errorf("body hash mismatch")
	}
	return nil
}
