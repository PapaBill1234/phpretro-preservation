package server

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestRoutes(t *testing.T) {
	// docs/evidence/F61-profile-http.md records the retained server.go demo smoke routes.
	handler := New()
	cases := []struct {
		path string
		want string
	}{
		{"/healthz", `"status":"ok"`},
		{"/", `<!doctype html>`},
		{"/home", `"username":"DemoUser"`},
		{"/account", `"status":"synthetic"`},
		{"/community", `"rooms":[{"ID":1,"Name":"Demo room"`},
		{"/articles", `"news":[{"ID":1,"Title":"Synthetic article"`},
		{"/api/profile", `"username":"DemoUser"`},
	}
	for _, tc := range cases {
		t.Run(tc.path, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tc.path, nil)
			res := httptest.NewRecorder()
			handler.ServeHTTP(res, req)
			if res.Code != http.StatusOK {
				t.Fatalf("GET %s status = %d, want 200; body=%s", tc.path, res.Code, res.Body.String())
			}
			if !strings.Contains(res.Body.String(), tc.want) {
				t.Fatalf("GET %s body %q does not contain %q", tc.path, res.Body.String(), tc.want)
			}
			if tc.path != "/healthz" && tc.path != "/" {
				var value map[string]any
				if err := json.Unmarshal(res.Body.Bytes(), &value); err != nil {
					t.Fatalf("GET %s returned invalid JSON: %v", tc.path, err)
				}
			}
		})
	}
}

func TestUnknownRouteNotFound(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/not-a-route", nil)
	res := httptest.NewRecorder()
	New().ServeHTTP(res, req)
	if res.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", res.Code)
	}
}

func TestServerStartsAndAnswersHealth(t *testing.T) {
	srv := httptest.NewServer(New())
	defer srv.Close()
	res, err := http.Get(srv.URL + "/healthz")
	if err != nil {
		t.Fatalf("GET /healthz: %v", err)
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", res.StatusCode)
	}
}
