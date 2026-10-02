// Package content contains the read-only hotel news boundary.
package content

import "fmt"

type ButtonType string

const (
	ButtonClient ButtonType = "client"
	ButtonWeb    ButtonType = "web"
)

type News struct {
	ID         int64
	Title      string
	Text       string
	ButtonText string
	ButtonType ButtonType
	ButtonLink string
	Image      string
}

type Store interface {
	ListNews(limit int) ([]News, error)
}

type Service struct{ Store Store }

func (s Service) News() ([]News, error) {
	if s.Store == nil {
		return nil, fmt.Errorf("content store unavailable")
	}
	rows, err := s.Store.ListNews(10)
	if err != nil {
		return nil, err
	}
	if len(rows) > 10 {
		rows = rows[:10]
	}
	for _, row := range rows {
		if row.ButtonType != ButtonClient && row.ButtonType != ButtonWeb {
			return nil, fmt.Errorf("unknown news button type %q", row.ButtonType)
		}
	}
	return rows, nil
}
