package staff

import (
	"encoding/base32"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
)

var (
	ErrMissingCode   = errors.New("missing TOTP code")
	ErrDisabled      = errors.New("staff account disabled")
	ErrMalformedCode = errors.New("malformed TOTP code")
	ErrWrongCode     = errors.New("wrong TOTP code")
	ErrExpiredCode   = errors.New("expired TOTP code")
	ErrWrongUser     = errors.New("wrong staff user")
	ErrStore         = errors.New("staff store failure")
)

type Record struct {
	StaffID string
	Secret  string
	Enabled bool
}
type Store interface {
	Lookup(staffID string) (Record, error)
}
type MemoryStore struct {
	Records map[string]Record
	Err     error
}

func (s *MemoryStore) Lookup(id string) (Record, error) {
	if s.Err != nil {
		return Record{}, s.Err
	}
	r, ok := s.Records[id]
	if !ok {
		return Record{}, ErrWrongUser
	}
	return r, nil
}

// ValidateCode uses library-backed RFC 6238 TOTP with a synthetic 30-second
// period and zero accepted clock skew. Secrets are synthetic base32 values;
// no secret is returned or persisted by validation. Timing policy is unapproved.
func ValidateCode(store Store, staffID, code string, now time.Time) error {
	if staffID == "" {
		return ErrWrongUser
	}
	if strings.TrimSpace(code) == "" {
		return ErrMissingCode
	}
	if len(code) != 6 {
		return ErrMalformedCode
	}
	for _, c := range code {
		if c < '0' || c > '9' {
			return ErrMalformedCode
		}
	}
	r, err := store.Lookup(staffID)
	if err != nil {
		if errors.Is(err, ErrWrongUser) {
			return ErrWrongUser
		}
		return fmt.Errorf("%w: %v", ErrStore, err)
	}
	if !r.Enabled {
		return ErrDisabled
	}
	if r.StaffID == "" || r.StaffID != staffID {
		return ErrWrongUser
	}
	secret, err := base32.StdEncoding.WithPadding(base32.NoPadding).DecodeString(strings.ToUpper(strings.TrimSpace(r.Secret)))
	if err != nil || len(secret) == 0 {
		return ErrMalformedCode
	}
	secretText := strings.ToUpper(strings.TrimSpace(r.Secret))
	opts := totp.ValidateOpts{Period: 30, Skew: 0, Digits: otp.DigitsSix, Algorithm: otp.AlgorithmSHA1}
	if valid, err := totp.ValidateCustom(code, secretText, now, opts); err != nil {
		return ErrMalformedCode
	} else if valid {
		return nil
	}
	// Distinguish adjacent-step codes for a stable expired result while keeping
	// them rejected. The library performs all TOTP computation.
	for _, adjacent := range []time.Time{now.Add(-30 * time.Second), now.Add(30 * time.Second)} {
		if valid, _ := totp.ValidateCustom(code, secretText, adjacent, opts); valid {
			return ErrExpiredCode
		}
	}
	return ErrWrongCode
}

// SyntheticCode is test-fixture support and intentionally not an enrollment API.
func SyntheticCode(secret string, now time.Time) (string, error) {
	if _, err := base32.StdEncoding.WithPadding(base32.NoPadding).DecodeString(strings.ToUpper(strings.TrimSpace(secret))); err != nil {
		return "", err
	}
	return totp.GenerateCodeCustom(strings.ToUpper(strings.TrimSpace(secret)), now, totp.ValidateOpts{Period: 30, Digits: otp.DigitsSix, Algorithm: otp.AlgorithmSHA1})
}
