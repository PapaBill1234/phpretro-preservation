package content

import "testing"

type syntheticStore struct {
	rows  []News
	err   error
	limit int
}

func (s *syntheticStore) ListNews(limit int) ([]News, error) { s.limit = limit; return s.rows, s.err }

func TestNewsCapsAtTenAndPassesTypes(t *testing.T) {
	rows := make([]News, 12)
	for i := range rows {
		rows[i] = News{ID: int64(12 - i), ButtonType: ButtonWeb}
	}
	store := &syntheticStore{rows: rows}
	got, err := (Service{Store: store}).News()
	if err != nil || len(got) != 10 || store.limit != 10 {
		t.Fatalf("rows=%d limit=%d err=%v", len(got), store.limit, err)
	}
}

func TestNewsRejectsUnknownType(t *testing.T) {
	_, err := (Service{Store: &syntheticStore{rows: []News{{ID: 1, ButtonType: "unknown"}}}}).News()
	if err == nil {
		t.Fatal("expected unknown button type error")
	}
}

func TestNewsAcceptsClientType(t *testing.T) {
	got, err := (Service{Store: &syntheticStore{rows: []News{{ID: 1, ButtonType: ButtonClient}}}}).News()
	if err != nil || len(got) != 1 || got[0].ButtonType != ButtonClient {
		t.Fatalf("rows=%#v err=%v", got, err)
	}
}
