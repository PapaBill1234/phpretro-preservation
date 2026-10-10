package server

import (
	"encoding/json"
	"errors"
	"net/http/httptest"
	"reflect"
	"testing"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/profile"
)

type profileCall struct {
	ID       int64
	Username string
}
type recordingProfileStore struct {
	calls []profileCall
	rows  map[profileCall]profile.Profile
	err   error
}

func (s *recordingProfileStore) FindByID(id int64) (profile.Profile, error) {
	return s.find(profileCall{ID: id})
}
func (s *recordingProfileStore) FindByUsername(name string) (profile.Profile, error) {
	return s.find(profileCall{Username: name})
}
func (s *recordingProfileStore) find(c profileCall) (profile.Profile, error) {
	s.calls = append(s.calls, c)
	if s.err != nil {
		return profile.Profile{}, s.err
	}
	return s.rows[c], nil
}

func TestInjectedProfileSelections(t *testing.T) {
	// docs/roadmap/restart-contracts.md F61; public fields: docs/evidence/F3-profile-schema.md.
	created := time.Date(2020, 1, 2, 3, 4, 5, 0, time.UTC)
	a := profile.Profile{ID: 7, Username: "Alpha", Motto: "hello", Look: "figure-a", Gender: "M", AccountCreated: created}
	b := profile.Profile{ID: 9, Username: "Beta_-2", Motto: "bye", Look: "figure-b", Gender: "F", AccountCreated: created}
	store := &recordingProfileStore{rows: map[profileCall]profile.Profile{{ID: 7}: a, {Username: "Beta_-2"}: b}}
	handler := NewWithProfileStore(store)
	for _, tc := range []struct {
		url string
		row profile.Profile
	}{{"/api/profile?id=007&tab=invalid", a}, {"/api/profile?username=%20Beta_-2%20", b}} {
		res := httptest.NewRecorder()
		handler.ServeHTTP(res, httptest.NewRequest("GET", tc.url, nil))
		if res.Code != 200 {
			t.Fatalf("selected profile status=%d body=%s", res.Code, res.Body.String())
		}
		var got map[string]any
		if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
			t.Fatal(err)
		}
		want := map[string]any{"version": "profile.v1", "tab": float64(1), "profile": map[string]any{"id": float64(tc.row.ID), "username": tc.row.Username, "motto": tc.row.Motto, "look": tc.row.Look, "gender": tc.row.Gender, "accountCreated": "2020-01-02T03:04:05Z"}}
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("public DTO = %#v, want %#v", got, want)
		}
	}
	if !reflect.DeepEqual(store.calls, []profileCall{{ID: 7}, {Username: "Beta_-2"}}) {
		t.Fatalf("exact selection calls=%v", store.calls)
	}
}

func TestRejectedProfileSelectionsNeverCallStore(t *testing.T) {
	// docs/roadmap/restart-contracts.md F61 rejects missing, ambiguous, duplicate and invalid selections.
	for _, query := range []string{"", "tab=1", "id=", "id=0", "id=-1", "id=%2B1", "id=1.0", "id=%201", "id=9223372036854775808", "id=1&id=2", "username=a&username=a", "id=1&username=", "id=&username=a", "username=", "username=%20", "username=a.b", "username=a%2Fb", "username=%C3%A9", "username=abcdefghijklmnopqrstuvwxyz1234567", "id=1;username=a"} {
		t.Run(query, func(t *testing.T) {
			store := &recordingProfileStore{}
			res := httptest.NewRecorder()
			NewWithProfileStore(store).ServeHTTP(res, httptest.NewRequest("GET", "/api/profile?"+query, nil))
			if res.Code != 400 {
				t.Fatalf("invalid selection status=%d want 400", res.Code)
			}
			if len(store.calls) != 0 {
				t.Fatalf("invalid selection called store: %v", store.calls)
			}
		})
	}
}

func TestProfileFailuresAreGeneric(t *testing.T) {
	// docs/roadmap/restart-contracts.md F61: known missing 404; nil/unavailable/malformed 503, no private fields.
	for _, tc := range []struct {
		name   string
		store  profile.Store
		status int
	}{
		{"nil", nil, 503},
		{"missing", &recordingProfileStore{err: profile.ErrNotFound}, 404},
		{"wrapped missing", &recordingProfileStore{err: errors.Join(errors.New("sensitive diagnostic"), profile.ErrNotFound)}, 404},
		{"outage", &recordingProfileStore{err: errors.New("sensitive diagnostic")}, 503},
		{"unavailable", &recordingProfileStore{err: profile.ErrStoreUnavailable}, 503},
		{"zero row", &recordingProfileStore{}, 503},
		{"empty username", &recordingProfileStore{rows: map[profileCall]profile.Profile{{ID: 1}: {ID: 1, Gender: "M"}}}, 503},
		{"bad gender", &recordingProfileStore{rows: map[profileCall]profile.Profile{{ID: 1}: {ID: 1, Username: "Synthetic", Gender: "X"}}}, 503},
	} {
		t.Run(tc.name, func(t *testing.T) {
			res := httptest.NewRecorder()
			NewWithProfileStore(tc.store).ServeHTTP(res, httptest.NewRequest("GET", "/api/profile?id=1", nil))
			if res.Code != tc.status {
				t.Fatalf("failure status=%d want %d", res.Code, tc.status)
			}
			var got map[string]string
			if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
				t.Fatal(err)
			}
			message := "profile unavailable"
			if tc.status == 404 {
				message = "profile not found"
			}
			if !reflect.DeepEqual(got, map[string]string{"error": message}) {
				t.Fatalf("failure exposed non-generic payload: %v", got)
			}
		})
	}
}
