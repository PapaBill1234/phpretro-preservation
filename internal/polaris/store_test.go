package polaris

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/profile"
)

type fixture struct {
	queries []string
	args    [][]driver.Value
}

type fixtureDriver struct{ f *fixture }
type fixtureConn struct{ f *fixture }
type fixtureRows struct {
	columns []string
	values  [][]driver.Value
	at      int
}

func (d fixtureDriver) Open(string) (driver.Conn, error)  { return fixtureConn(d), nil }
func (c fixtureConn) Prepare(string) (driver.Stmt, error) { return nil, errors.New("prepare not used") }
func (c fixtureConn) Close() error                        { return nil }
func (c fixtureConn) Begin() (driver.Tx, error)           { return nil, errors.New("writes unavailable") }
func (c fixtureConn) QueryContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}
	c.f.queries = append(c.f.queries, query)
	got := make([]driver.Value, len(args))
	for i, a := range args {
		got[i] = a.Value
	}
	c.f.args = append(c.f.args, got)
	switch {
	case strings.Contains(query, "SELECT id, username, password"):
		if len(args) == 1 && args[0].Value == "db-error" {
			return nil, errors.New("synthetic database failure")
		}
		if len(args) != 1 || args[0].Value != "alice" {
			return &fixtureRows{columns: []string{"id", "username", "password"}}, nil
		}
		return &fixtureRows{columns: []string{"id", "username", "password"}, values: [][]driver.Value{{int64(7), "alice", "stored-verifier"}}}, nil
	case strings.Contains(query, "FROM users WHERE id"):
		if len(args) == 1 && args[0].Value == int64(1) {
			return &fixtureRows{columns: []string{"id", "username", "motto", "look", "gender", "account_created"}}, nil
		}
		return &fixtureRows{columns: []string{"id", "username", "motto", "look", "gender", "account_created"}, values: [][]driver.Value{{int64(7), "alice", "hello", "hd-1", "F", time.Date(2020, 1, 2, 3, 4, 5, 0, time.UTC)}}}, nil
	case strings.Contains(query, "FROM users WHERE username"):
		return &fixtureRows{columns: []string{"id", "username", "motto", "look", "gender", "account_created"}, values: [][]driver.Value{{int64(7), "alice", "hello", "hd-1", "F", time.Date(2020, 1, 2, 3, 4, 5, 0, time.UTC)}}}, nil
	case strings.Contains(query, "FROM hotelview_news"):
		return &fixtureRows{columns: []string{"id", "title", "text", "button_text", "button_type", "button_link", "image"}, values: [][]driver.Value{{int64(9), "Title", "Body", "Read", "web", "/news/9", "hero.png"}}}, nil
	default:
		return nil, errors.New("unexpected query")
	}
}
func (r *fixtureRows) Columns() []string { return r.columns }
func (r *fixtureRows) Close() error      { return nil }
func (r *fixtureRows) Next(dest []driver.Value) error {
	if r.at >= len(r.values) {
		return io.EOF
	}
	copy(dest, r.values[r.at])
	r.at++
	return nil
}

func openFixture(t *testing.T) (*fixture, *AccountStore, *ProfileStore, *ContentStore) {
	t.Helper()
	f := &fixture{}
	name := "polaris-fixture-" + strings.ReplaceAll(t.Name(), "/", "-")
	sql.Register(name, fixtureDriver{f})
	db, err := sql.Open(name, "")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return f, NewAccountStore(db), NewProfileStore(db), NewContentStore(db)
}

func TestStoreReadsWithExplicitQueriesAndBoundArguments(t *testing.T) {
	f, accounts, profiles, content := openFixture(t)
	u, verifier, err := accounts.FindByUsername("alice")
	if err != nil || u.ID != "7" || verifier != "stored-verifier" {
		t.Fatalf("account=%#v verifier=%q err=%v", u, verifier, err)
	}
	p, err := profiles.FindByUsername("alice")
	if err != nil || p.ID != 7 || p.Gender != "F" {
		t.Fatalf("profile=%#v err=%v", p, err)
	}
	rows, err := content.ListNews(999)
	if err != nil || len(rows) != 1 || rows[0].ID != 9 {
		t.Fatalf("news=%#v err=%v", rows, err)
	}
	if !reflect.DeepEqual(f.args, [][]driver.Value{{"alice"}, {"alice"}, {}}) {
		t.Fatalf("bound args=%#v", f.args)
	}
	wantQueries := []string{
		"SELECT id, username, password FROM users WHERE username = ? LIMIT 1",
		"SELECT id, username, motto, look, gender, account_created FROM users WHERE username = ? LIMIT 1",
		"SELECT id, title, text, button_text, button_type, button_link, image FROM hotelview_news ORDER BY id DESC LIMIT 10",
	}
	if !reflect.DeepEqual(f.queries, wantQueries) {
		t.Fatalf("queries=%#v want=%#v", f.queries, wantQueries)
	}
}

func TestStoreMapsNoRowsAndWrapsDatabaseErrors(t *testing.T) {
	_, accounts, profiles, _ := openFixture(t)
	if _, err := profiles.FindByID(1); !errors.Is(err, profile.ErrNotFound) {
		t.Fatalf("profile no-row error=%v", err)
	}
	if _, _, err := accounts.FindByUsername("missing"); err == nil {
		t.Fatal("expected account error")
	}
	if _, _, err := accounts.FindByUsername("db-error"); !strings.Contains(err.Error(), "find account by username") {
		t.Fatalf("database error=%v", err)
	}
}

func TestStoresRejectUnavailableDatabase(t *testing.T) {
	if _, _, err := (*AccountStore)(nil).FindByUsername("alice"); err == nil {
		t.Fatal("expected nil account store error")
	}
	if _, err := NewProfileStore(nil).FindByID(7); err == nil {
		t.Fatal("expected nil profile database error")
	}
	if _, err := NewContentStore(nil).ListNews(10); err == nil {
		t.Fatal("expected nil content database error")
	}
}
