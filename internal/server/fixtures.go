package server

import (
	"errors"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/accountview"
	"github.com/PapaBill1234/phpretro-preservation/internal/community"
	"github.com/PapaBill1234/phpretro-preservation/internal/home"
	"github.com/PapaBill1234/phpretro-preservation/internal/profile"
)

var errFixtureNotFound = errors.New("synthetic fixture not found")

// fixtures contains development-only records; no persistent or external source is used.
type fixtures struct {
	community community.Model
}

func newFixtures() fixtures {
	return fixtures{community: community.Model{
		Rooms:       []community.Room{{ID: 1, Name: "Demo room", Description: "Synthetic room", Owner: "DemoUser"}},
		Discussions: []community.Discussion{{ID: 1, Title: "Synthetic discussion", GroupID: 1}},
		News:        []community.News{{ID: 1, Title: "Synthetic article", Summary: "Development fixture", HeaderImage: "", Date: "2026-01-01"}},
		Tags:        []community.Tag{{Tag: "demo", Quantity: 1}},
	}}
}

func (fixtures) DashboardForPrincipal(id int64) (accountview.AccountView, error) {
	p := demoProfile()
	if id != p.ID {
		return accountview.AccountView{}, errFixtureNotFound
	}
	return accountview.AccountView{Profile: p, Status: "synthetic", Widgets: []accountview.Widget{}}, nil
}

type homeFixtures struct{ fixtures }

func (homeFixtures) FindByID(id int64) (home.Record, error) {
	if id != 1 {
		return home.Record{}, errFixtureNotFound
	}
	return home.Record{OwnerID: 1, Username: "DemoUser", ShowHome: true, PublicContent: "Synthetic public home"}, nil
}

func (homeFixtures) FindByUsername(username string) (home.Record, error) {
	if username != "DemoUser" {
		return home.Record{}, errFixtureNotFound
	}
	return home.Record{OwnerID: 1, Username: "DemoUser", ShowHome: true, PublicContent: "Synthetic public home"}, nil
}

type profileFixtures struct{ fixtures }

func (profileFixtures) FindByID(id int64) (profile.Profile, error) {
	if id != 1 {
		return profile.Profile{}, errFixtureNotFound
	}
	return demoProfile(), nil
}

func (profileFixtures) FindByUsername(username string) (profile.Profile, error) {
	if username != "DemoUser" {
		return profile.Profile{}, errFixtureNotFound
	}
	return demoProfile(), nil
}

func demoProfile() profile.Profile {
	return profile.Profile{ID: 1, Username: "DemoUser", Motto: "Synthetic profile", Look: "development-placeholder", Gender: "M", AccountCreated: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)}
}
