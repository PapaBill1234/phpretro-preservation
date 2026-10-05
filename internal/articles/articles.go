package articles

import (
	"html"
	"net/url"
	"strings"
)

// Article is the read-only public content shape. It has no CMS write operations.
type Article struct {
	Path      string
	Title     string
	Category  string
	ImageURL  string
	Summary   string
	Story     string
	Author    string
}

type Policy struct {
	ImageHosts []string
}

// Project returns a safe public projection without modifying the source slice.
func Project(source []Article, policy Policy) []Article {
	out := make([]Article, 0, len(source))
	for _, in := range source {
		if strings.TrimRight(in.Path, "/") == "/articles/archive" {
			continue
		}
		item := in
		item.Title = html.EscapeString(item.Title)
		item.Category = html.EscapeString(item.Category)
		item.Summary = html.EscapeString(item.Summary)
		item.Story = html.EscapeString(item.Story)
		item.Author = html.EscapeString(item.Author)
		if !allowedImage(item.ImageURL, policy.ImageHosts) {
			item.ImageURL = ""
		}
		out = append(out, item)
	}
	return out
}

func allowedImage(raw string, hosts []string) bool {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "https" || u.Host == "" || u.User != nil || u.Path == "" {
		return false
	}
	for _, host := range hosts {
		if strings.EqualFold(u.Host, host) {
			return true
		}
	}
	return false
}
