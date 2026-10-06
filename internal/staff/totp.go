package staff

import (
	"crypto/hmac"
	"crypto/sha1" // #nosec G505 -- RFC 6238 specifies HMAC-SHA1 for this synthetic contract.
	"crypto/subtle"
	"encoding/base32"
	"encoding/binary"
	"errors"
	"fmt"
	"strings"
	"time"
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

// ValidateCode uses RFC 6238 TOTP with a 30-second step and one approved adjacent step.
// Secrets are synthetic base32 values; no secret is returned or persisted by validation.
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
	step := now.Unix() / 30
	for _, candidate := range []int64{step - 1, step, step + 1} {
		if subtle.ConstantTimeCompare([]byte(totp(secret, candidate)), []byte(code)) == 1 {
			if candidate != step {
				return ErrExpiredCode
			}
			return nil
		}
	}
	return ErrWrongCode
}
func totp(secret []byte, counter int64) string {
	var b [8]byte
	binary.BigEndian.PutUint64(b[:], uint64(counter)) // #nosec G115 -- TOTP counters are non-negative in the approved window.
	h := hmac.New(sha1.New, secret)
	_, _ = h.Write(b[:])
	sum := h.Sum(nil)
	off := sum[len(sum)-1] & 15
	n := (uint32(sum[off])&127)<<24 | uint32(sum[off+1])<<16 | uint32(sum[off+2])<<8 | uint32(sum[off+3])
	return fmt.Sprintf("%06d", n%1000000)
}

// SyntheticCode is test-fixture support and intentionally not an enrollment API.
func SyntheticCode(secret string, now time.Time) (string, error) {
	b, err := base32.StdEncoding.WithPadding(base32.NoPadding).DecodeString(strings.ToUpper(secret))
	if err != nil {
		return "", err
	}
	return totp(b, now.Unix()/30), nil
}
