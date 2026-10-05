package community

import "testing"

func TestListBoundsRoomsAndPreservesEmptyState(t *testing.T) {
	model := Model{Rooms: []Room{{ID: 1, Name: "One"}, {ID: 2, Name: "Two"}, {ID: 3, Name: "Three"}}}
	got, err := model.List(KindRooms, Request{Limit: 2})
	if err != nil || len(got.Rooms) != 2 || got.Rooms[0].ID != 1 {
		t.Fatalf("result=%#v err=%v", got, err)
	}
	empty, err := (Model{}).List(KindTags, Request{Limit: 20})
	if err != nil || empty.Tags == nil || len(empty.Tags) != 0 {
		t.Fatalf("empty=%#v err=%v", empty, err)
	}
}

func TestListRejectsMalformedPagination(t *testing.T) {
	for _, request := range []Request{{Offset: -1, Limit: 1}, {Limit: 0}, {Limit: MaxPageSize + 1}} {
		if _, err := (Model{}).List(KindNews, request); err == nil {
			t.Fatalf("request %#v was accepted", request)
		}
	}
}

func TestListRejectsPrivateOrUnapprovedFields(t *testing.T) {
	for _, field := range []string{"email", "password", "created_at"} {
		if _, err := (Model{}).List(KindDiscussions, Request{Limit: 1, Fields: []string{field}}); err == nil {
			t.Fatalf("field %q was accepted", field)
		}
	}
}

func TestListAcceptsSourceBackedFields(t *testing.T) {
	model := Model{News: []News{{ID: 7, Title: "Headline", Summary: "Brief", HeaderImage: "header.png", Date: "Jan 1, 2024"}}}
	got, err := model.List(KindNews, Request{Limit: 1, Fields: []string{"id", "title", "summary", "header_image", "date"}})
	if err != nil || len(got.News) != 1 || got.News[0].ID != 7 {
		t.Fatalf("result=%#v err=%v", got, err)
	}
}
