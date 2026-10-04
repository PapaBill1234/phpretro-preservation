package profile

import (
	"reflect"
	"testing"
)

func TestNormalizeTab(t *testing.T) {
	cases := []struct {
		name string
		raw  string
		want Tab
	}{
		{"absent empty string", "", TabDefault},
		{"tab 1", "1", 1},
		{"tab 2", "2", 2},
		{"tab 3", "3", 3},
		{"tab 4", "4", 4},
		{"tab 5", "5", 5},
		{"below range zero", "0", TabDefault},
		{"above range six", "6", TabDefault},
		{"negative", "-1", TabDefault},
		{"non-integer", "abc", TabDefault},
		{"whitespace padded valid", " 3 ", 3},
		{"fractional", "1.5", TabDefault},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := NormalizeTab(tc.raw); got != tc.want {
				t.Fatalf("NormalizeTab(%q) = %d, want %d", tc.raw, got, tc.want)
			}
		})
	}
}

func TestNewViewPreservesProfileFields(t *testing.T) {
	p := syntheticProfile()
	got := NewView(p, "4")
	if !reflect.DeepEqual(got.Profile, p) {
		t.Fatalf("View.Profile = %#v, want unchanged %#v", got.Profile, p)
	}
	if got.Tab != 4 {
		t.Fatalf("View.Tab = %d, want 4", got.Tab)
	}
}

func TestNewViewTabMatchesNormalizeTab(t *testing.T) {
	p := syntheticProfile()
	for _, raw := range []string{"", "1", "5", "0", "6", "-1", "abc", " 3 ", "1.5"} {
		got := NewView(p, raw)
		if want := NormalizeTab(raw); got.Tab != want {
			t.Fatalf("NewView(%q).Tab = %d, want %d", raw, got.Tab, want)
		}
	}
}

func TestNewViewAbsentDefaultsToTabOne(t *testing.T) {
	if got := NewView(syntheticProfile(), ""); got.Tab != TabDefault {
		t.Fatalf("NewView(absent).Tab = %d, want %d", got.Tab, TabDefault)
	}
}

func TestNewViewInvalidDefaultsToTabOne(t *testing.T) {
	if got := NewView(syntheticProfile(), "9"); got.Tab != TabDefault {
		t.Fatalf("NewView(invalid).Tab = %d, want %d", got.Tab, TabDefault)
	}
}
