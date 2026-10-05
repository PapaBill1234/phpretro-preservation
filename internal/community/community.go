// Package community contains the guest-readable, read-only community projection.
package community

import (
	"errors"
	"fmt"
)

const MaxPageSize = 20

var ErrInvalidRequest = errors.New("invalid community request")

type Kind string

const (
	KindRooms       Kind = "rooms"
	KindDiscussions Kind = "discussions"
	KindNews        Kind = "news"
	KindTags        Kind = "tags"
)

type Request struct {
	Offset int
	Limit  int
	Fields []string
}

type Room struct {
	ID          int64
	Name        string
	Description string
	Owner       string
}

type Discussion struct {
	ID      int64
	Title   string
	GroupID int64
}

type News struct {
	ID          int64
	Title       string
	Summary     string
	HeaderImage string
	Date        string
}

type Tag struct {
	Tag      string
	Quantity int
}

type Result struct {
	Rooms       []Room
	Discussions []Discussion
	News        []News
	Tags        []Tag
}

type Model struct {
	Rooms       []Room
	Discussions []Discussion
	News        []News
	Tags        []Tag
}

// List returns only synthetic, public fields observed in community.php. It
// does not infer storage, identity, authorization, or private columns.
func (m Model) List(kind Kind, request Request) (Result, error) {
	if request.Offset < 0 || request.Limit < 1 || request.Limit > MaxPageSize {
		return Result{}, fmt.Errorf("%w: offset=%d limit=%d", ErrInvalidRequest, request.Offset, request.Limit)
	}
	if !allowedFields(kind, request.Fields) {
		return Result{}, fmt.Errorf("%w: fields for %s", ErrInvalidRequest, kind)
	}
	result := Result{}
	switch kind {
	case KindRooms:
		result.Rooms = page(m.Rooms, request.Offset, request.Limit)
	case KindDiscussions:
		result.Discussions = page(m.Discussions, request.Offset, request.Limit)
	case KindNews:
		result.News = page(m.News, request.Offset, request.Limit)
	case KindTags:
		result.Tags = page(m.Tags, request.Offset, request.Limit)
	default:
		return Result{}, fmt.Errorf("%w: kind %q", ErrInvalidRequest, kind)
	}
	return result, nil
}

func page[T any](rows []T, offset, limit int) []T {
	if offset >= len(rows) {
		return []T{}
	}
	end := offset + limit
	if end > len(rows) {
		end = len(rows)
	}
	return rows[offset:end]
}

func allowedFields(kind Kind, fields []string) bool {
	if len(fields) == 0 {
		return true
	}
	allowed := map[Kind]map[string]bool{
		KindRooms:       {"id": true, "name": true, "description": true, "owner": true},
		KindDiscussions: {"id": true, "title": true, "group_id": true},
		KindNews:        {"id": true, "title": true, "summary": true, "header_image": true, "date": true},
		KindTags:        {"tag": true, "quantity": true},
	}[kind]
	if allowed == nil {
		return false
	}
	for _, field := range fields {
		if !allowed[field] {
			return false
		}
	}
	return true
}
