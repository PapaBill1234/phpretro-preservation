package home

import (
	"errors"
	"testing"
)

type syntheticStore struct{ record Record; err error; byID, byUsername Record }
func (s syntheticStore) FindByID(int64) (Record, error) { if s.byID.OwnerID != 0 { return s.byID, s.err }; return s.record, s.err }
func (s syntheticStore) FindByUsername(string) (Record, error) { if s.byUsername.OwnerID != 0 { return s.byUsername, s.err }; return s.record, s.err }

func publicRecord() Record {
	return Record{OwnerID: 7, Username: "synthetic-user", ShowHome: true, PublicContent: "public"}
}

func TestReadByIDAndUsername(t *testing.T) {
	store := syntheticStore{record: publicRecord()}
	for name, lookup := range map[string]Lookup{"id": {ID: 7}, "username": {Username: " synthetic-user "}} {
		t.Run(name, func(t *testing.T) {
			view, err := (Service{Store: store}).Read(lookup, Viewer{})
			if err != nil || view.Username != "synthetic-user" || view.PublicContent != "public" {
				t.Fatalf("view = %#v, err = %v", view, err)
			}
		})
	}
}

func TestPrivateHomeHidesContentFromOtherViewer(t *testing.T) {
	record := publicRecord()
	record.ShowHome = false
	view, err := (Service{Store: syntheticStore{record: record}}).Read(Lookup{ID: 7}, Viewer{OwnerID: 8})
	if !errors.Is(err, ErrUnsupportedState) || view != (View{}) {
		t.Fatalf("view = %#v, err = %v", view, err)
	}
}

func TestPrivateHomeIsVisibleToOwner(t *testing.T) {
	record := publicRecord()
	record.ShowHome = false
	view, err := (Service{Store: syntheticStore{record: record}}).Read(Lookup{ID: 7}, Viewer{OwnerID: 7})
	if err != nil || view.PublicContent != "public" {
		t.Fatalf("view = %#v, err = %v", view, err)
	}
}

func TestRejectsMalformedLookupAndUnknownOwner(t *testing.T) {
	service := Service{Store: syntheticStore{record: publicRecord()}}
	for _, lookup := range []Lookup{{}, {ID: 7, Username: "synthetic-user"}, {ID: -1}} {
		if _, err := service.Read(lookup, Viewer{}); !errors.Is(err, ErrInvalidLookup) {
			t.Fatalf("lookup %#v error = %v", lookup, err)
		}
	}
	_, err := (Service{Store: syntheticStore{err: ErrNotFound}}).Read(Lookup{ID: 7}, Viewer{})
	if !errors.Is(err, ErrNotFound) { t.Fatalf("error = %v", err) }
}

func TestRejectsUnsupportedRecordState(t *testing.T) {
	_, err := (Service{Store: syntheticStore{record: Record{OwnerID: 7}}}).Read(Lookup{ID: 7}, Viewer{})
	if !errors.Is(err, ErrNotFound) { t.Fatalf("error = %v", err) }
}
