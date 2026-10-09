package server

import (
	"errors"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/PapaBill1234/phpretro-preservation/internal/profile"
)

func profileHandler(store profile.Store, demo bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		query, err := url.ParseQuery(r.URL.RawQuery)
		if err != nil {
			profileError(w, http.StatusBadRequest)
			return
		}
		ids, hasID := query["id"]
		names, hasName := query["username"]
		// Only the explicit demo constructor preserves the historical no-selection smoke route.
		if demo && !hasID && !hasName {
			ids, hasID = []string{"1"}, true
		}
		if hasID == hasName {
			profileError(w, http.StatusBadRequest)
			return
		}
		var id int64
		var name string
		if hasID {
			if len(ids) != 1 || ids[0] == "" {
				profileError(w, 400)
				return
			}
			for _, c := range ids[0] {
				if c < '0' || c > '9' {
					profileError(w, 400)
					return
				}
			}
			id, err = strconv.ParseInt(ids[0], 10, 64)
			if err != nil || id <= 0 {
				profileError(w, 400)
				return
			}
		} else {
			if len(names) != 1 {
				profileError(w, 400)
				return
			}
			name = strings.TrimSpace(names[0])
			if len(name) < 1 || len(name) > 32 {
				profileError(w, 400)
				return
			}
			for _, c := range name {
				if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '_' || c == '-') {
					profileError(w, 400)
					return
				}
			}
		}
		if store == nil {
			profileError(w, 503)
			return
		}
		var p profile.Profile
		if hasID {
			p, err = store.FindByID(id)
		} else {
			p, err = store.FindByUsername(name)
		}
		if err != nil {
			if errors.Is(err, profile.ErrNotFound) {
				profileError(w, 404)
			} else {
				profileError(w, 503)
			}
			return
		}
		// A successful but malformed row is not a confirmed missing profile.
		if p.ID <= 0 || strings.TrimSpace(p.Username) == "" || (p.Gender != "M" && p.Gender != "F") {
			profileError(w, 503)
			return
		}
		writeJSON(w, http.StatusOK, profilePayload(profile.NewView(p, query.Get("tab"))))
	}
}

func profileError(w http.ResponseWriter, status int) {
	message := "profile unavailable"
	switch status {
	case http.StatusBadRequest:
		message = "invalid profile selection"
	case http.StatusNotFound:
		message = "profile not found"
	}
	writeJSON(w, status, map[string]string{"error": message})
}
