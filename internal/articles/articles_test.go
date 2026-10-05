package articles

import (
	"strings"
	"testing"
)

func TestProjectExcludesArchiveRoute(t *testing.T) {
	// Evidence: docs/roadmap/F18-F30-feature-approval.md, line 47 reserves the archive route for F17.
	got := Project([]Article{{Path: "/articles/archive", Title: "Archive"}, {Path: "/articles/42", Title: "Visible"}}, Policy{})
	if len(got) != 1 || got[0].Title != "Visible" {
		t.Fatalf("archive route was projected: %#v", got)
	}
}

func TestProjectEscapesText(t *testing.T) {
	// Evidence: docs/roadmap/F18-F30-feature-approval.md, line 47 identifies title, summary, and story rendering.
	got := Project([]Article{{Path: "/articles/1", Title: "<script>alert(1)</script>", Summary: `a & "b"`}}, Policy{})
	if strings.Contains(got[0].Title, "<script>") || got[0].Title != "&lt;script&gt;alert(1)&lt;/script&gt;" {
		t.Fatalf("title was not escaped: %q", got[0].Title)
	}
	if got[0].Summary != "a &amp; &#34;b&#34;" {
		t.Fatalf("summary was not escaped: %q", got[0].Summary)
	}
}

func TestProjectAllowlistsImageURLs(t *testing.T) {
	// Evidence: docs/roadmap/F18-F30-feature-approval.md, line 47 requires a safe image URL contract.
	got := Project([]Article{
		{Path: "/articles/1", ImageURL: "https://cdn.example.test/image.jpg"},
		{Path: "/articles/2", ImageURL: "https://evil.example/image.jpg"},
		{Path: "/articles/3", ImageURL: "javascript:alert(1)"},
	}, Policy{ImageHosts: []string{"cdn.example.test"}})
	if got[0].ImageURL == "" || got[1].ImageURL != "" || got[2].ImageURL != "" {
		t.Fatalf("unexpected image projection: %#v", got)
	}
}

func TestProjectDoesNotMutateCMSInput(t *testing.T) {
	// Evidence: docs/roadmap/F18-F30-feature-approval.md, line 47 explicitly requires no CMS mutations.
	input := []Article{{Path: "/articles/1", Title: "Original"}}
	before := input[0]
	_ = Project(input, Policy{})
	if input[0] != before {
		t.Fatalf("project mutated CMS input: %#v", input)
	}
}
