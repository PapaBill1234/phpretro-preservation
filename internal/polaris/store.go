// Package polaris provides a disposable, read-only adapter for the PolarIS schema.
package polaris

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	"github.com/PapaBill1234/phpretro-preservation/internal/account"
	"github.com/PapaBill1234/phpretro-preservation/internal/content"
	"github.com/PapaBill1234/phpretro-preservation/internal/profile"
)

var errDatabaseUnavailable = errors.New("polaris database unavailable")

// AccountStore, ProfileStore, and ContentStore implement the existing contracts.
type AccountStore struct{ db *sql.DB }
type ProfileStore struct{ db *sql.DB }
type ContentStore struct{ db *sql.DB }

var (
	_ account.Store = (*AccountStore)(nil)
	_ profile.Store = (*ProfileStore)(nil)
	_ content.Store = (*ContentStore)(nil)
)

// NewStore creates a read-only adapter over an injected database handle.
func NewAccountStore(db *sql.DB) *AccountStore { return &AccountStore{db: db} }
func NewProfileStore(db *sql.DB) *ProfileStore { return &ProfileStore{db: db} }
func NewContentStore(db *sql.DB) *ContentStore { return &ContentStore{db: db} }

func (s *AccountStore) FindByUsername(username string) (account.User, string, error) {
	if s == nil || s.db == nil {
		return account.User{}, "", fmt.Errorf("find account by username: %w", errDatabaseUnavailable)
	}
	var id int64
	var name, password string
	err := s.db.QueryRowContext(context.Background(), `SELECT id, username, password FROM users WHERE username = ? LIMIT 1`, username).Scan(&id, &name, &password)
	if err != nil {
		return account.User{}, "", fmt.Errorf("find account by username: %w", err)
	}
	return account.User{ID: fmt.Sprint(id), Username: name}, password, nil
}

func (s *ProfileStore) FindByID(id int64) (profile.Profile, error) {
	if s == nil || s.db == nil {
		return profile.Profile{}, fmt.Errorf("find profile by id: %w", errDatabaseUnavailable)
	}
	var p profile.Profile
	err := s.db.QueryRowContext(context.Background(), `SELECT id, username, motto, look, gender, account_created FROM users WHERE id = ? LIMIT 1`, id).Scan(&p.ID, &p.Username, &p.Motto, &p.Look, &p.Gender, &p.AccountCreated)
	if err != nil {
		if err == sql.ErrNoRows {
			return profile.Profile{}, profile.ErrNotFound
		}
		return profile.Profile{}, fmt.Errorf("find profile by id: %w", err)
	}
	return p, nil
}

func (s *ProfileStore) FindByUsername(username string) (profile.Profile, error) {
	if s == nil || s.db == nil {
		return profile.Profile{}, fmt.Errorf("find profile by username: %w", errDatabaseUnavailable)
	}
	var p profile.Profile
	err := s.db.QueryRowContext(context.Background(), `SELECT id, username, motto, look, gender, account_created FROM users WHERE username = ? LIMIT 1`, username).Scan(&p.ID, &p.Username, &p.Motto, &p.Look, &p.Gender, &p.AccountCreated)
	if err != nil {
		if err == sql.ErrNoRows {
			return profile.Profile{}, profile.ErrNotFound
		}
		return profile.Profile{}, fmt.Errorf("find profile by username: %w", err)
	}
	return p, nil
}

func (s *ContentStore) ListNews(limit int) ([]content.News, error) {
	if s == nil || s.db == nil {
		return nil, fmt.Errorf("list hotel news: %w", errDatabaseUnavailable)
	}
	rows, err := s.db.QueryContext(context.Background(), `SELECT id, title, text, button_text, button_type, button_link, image FROM hotelview_news ORDER BY id DESC LIMIT 10`)
	if err != nil {
		return nil, fmt.Errorf("list hotel news: %w", err)
	}
	defer rows.Close()
	var result []content.News
	for rows.Next() {
		var n content.News
		if err := rows.Scan(&n.ID, &n.Title, &n.Text, &n.ButtonText, &n.ButtonType, &n.ButtonLink, &n.Image); err != nil {
			return nil, fmt.Errorf("scan hotel news: %w", err)
		}
		result = append(result, n)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate hotel news: %w", err)
	}
	return result, nil
}
