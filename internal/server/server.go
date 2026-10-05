package server

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/PapaBill1234/phpretro-preservation/internal/accountview"
	"github.com/PapaBill1234/phpretro-preservation/internal/authflow"
	"github.com/PapaBill1234/phpretro-preservation/internal/community"
	"github.com/PapaBill1234/phpretro-preservation/internal/home"
	"github.com/PapaBill1234/phpretro-preservation/internal/profile"
	"github.com/PapaBill1234/phpretro-preservation/internal/session"
)

// New builds the HTTP handler using only synthetic in-memory read models.
func New() http.Handler {
	mux := http.NewServeMux()
	fixtures := newFixtures()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /home", func(w http.ResponseWriter, r *http.Request) {
		view, err := (home.Service{Store: homeFixtures{fixtures}}).Read(home.Lookup{Username: "DemoUser"}, home.Viewer{})
		if err == nil {
			respond(w, map[string]any{"version": "home.v1", "ownerId": view.OwnerID, "username": view.Username, "publicContent": view.PublicContent}, nil)
			return
		}
		respond(w, nil, err)
	})
	mux.HandleFunc("GET /account", func(w http.ResponseWriter, r *http.Request) {
		view, err := (accountview.Service{Source: fixtures}).Read(accountview.Principal{ID: 1})
		if err == nil {
			respond(w, accountPayload(view), nil)
			return
		}
		respond(w, nil, err)
	})
	mux.HandleFunc("GET /community", func(w http.ResponseWriter, r *http.Request) {
		result, err := fixtures.community.List(community.KindRooms, community.Request{Limit: community.MaxPageSize})
		respond(w, communityPayload(result), err)
	})
	mux.HandleFunc("GET /articles", func(w http.ResponseWriter, r *http.Request) {
		result, err := fixtures.community.List(community.KindNews, community.Request{Limit: community.MaxPageSize})
		if err != nil {
			respond(w, nil, err)
			return
		}
		respond(w, map[string]any{"version": "articles.v1", "news": result.News}, nil)
	})
	mux.HandleFunc("GET /api/profile", func(w http.ResponseWriter, r *http.Request) {
		p, err := (profile.Service{Store: profileFixtures{fixtures}}).ByID(1)
		if err == nil {
			respond(w, profilePayload(profile.NewView(p, r.URL.Query().Get("tab"))), nil)
			return
		}
		respond(w, nil, err)
	})
	mux.HandleFunc("GET /api/auth/failed", func(w http.ResponseWriter, r *http.Request) {
		respond(w, authflow.FailedLoginResponse(), nil)
	})
	mux.HandleFunc("GET /api/auth/success", func(w http.ResponseWriter, r *http.Request) {
		respond(w, authflow.SuccessfulSubmitResponse(), nil)
	})
	mux.HandleFunc("GET /api/session/post-logout", func(w http.ResponseWriter, r *http.Request) {
		respond(w, (&session.Manager{}).PostLogoutPage(""), nil)
	})
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PHPRetro</title></head><body><div id="root"></div><script type="module" src="/frontend/src/main.tsx"></script></body></html>`))
	})
	return mux
}

func accountPayload(view accountview.AccountView) map[string]any {
	p := view.Profile
	return map[string]any{"version": "account.v1", "profile": map[string]any{"id": p.ID, "username": p.Username, "motto": p.Motto, "look": p.Look, "gender": p.Gender, "accountCreated": p.AccountCreated.Format("2006-01-02T15:04:05Z07:00")}, "status": view.Status, "widgets": view.Widgets}
}

func profilePayload(view profile.View) map[string]any {
	p := view.Profile
	return map[string]any{"version": "profile.v1", "profile": map[string]any{"id": p.ID, "username": p.Username, "motto": p.Motto, "look": p.Look, "gender": p.Gender, "accountCreated": p.AccountCreated.Format("2006-01-02T15:04:05Z07:00")}, "tab": int(view.Tab)}
}

func communityPayload(result community.Result) map[string]any {
	return map[string]any{"version": "community.v1", "rooms": result.Rooms, "discussions": result.Discussions, "news": result.News, "tags": result.Tags}
}

func respond(w http.ResponseWriter, value any, err error) {
	if err != nil {
		status := http.StatusInternalServerError
		if errors.Is(err, profile.ErrNotFound) || errors.Is(err, home.ErrNotFound) {
			status = http.StatusNotFound
		}
		writeJSON(w, status, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, value)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = jsonEncode(w, value)
}

// jsonEncode is isolated here to keep all response paths using the standard JSON encoder.
func jsonEncode(w http.ResponseWriter, value any) error {
	return json.NewEncoder(w).Encode(value)
}

// PortFromEnv normalizes the port configuration and rejects invalid values.
func PortFromEnv(raw string) (string, error) {
	if strings.TrimSpace(raw) == "" {
		return "8080", nil
	}
	port, err := strconv.Atoi(raw)
	if err != nil || port < 1 || port > 65535 {
		return "", fmt.Errorf("invalid PORT %q: expected 1-65535", raw)
	}
	return strconv.Itoa(port), nil
}
