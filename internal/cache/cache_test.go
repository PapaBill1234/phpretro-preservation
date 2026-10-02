package cache

import (
	"context"
	"testing"
	"time"
)

type fixture struct {
	Name  string
	Count int
}

func TestMemoryExpiryAndSerialization(t *testing.T) {
	m := NewMemory(time.Unix(100, 0))
	s := New(m)
	want := fixture{"synthetic", 1}
	if err := s.Put(context.Background(), NamespaceRead, "home", want, time.Second); err != nil {
		t.Fatal(err)
	}
	var got fixture
	ok, err := s.Get(context.Background(), NamespaceRead, "home", &got)
	if err != nil || !ok || got != want {
		t.Fatalf("got %#v ok=%v err=%v", got, ok, err)
	}
	m.Advance(time.Second)
	ok, err = s.Get(context.Background(), NamespaceRead, "home", &got)
	if err != nil || ok {
		t.Fatalf("expired ok=%v err=%v", ok, err)
	}
}
func TestRejectsNamespaceAndMalformedSerialization(t *testing.T) {
	m := NewMemory(time.Unix(100, 0))
	s := New(m)
	if err := s.Put(context.Background(), "phpretro:wrong:", "x", fixture{}, time.Second); err != ErrNamespace {
		t.Fatalf("err=%v", err)
	}
	m.data[NamespaceRead+"bad"] = entry{value: []byte("{"), expires: m.now.Add(time.Second)}
	var out fixture
	ok, err := s.Get(context.Background(), NamespaceRead, "bad", &out)
	if ok || err == nil {
		t.Fatalf("ok=%v err=%v", ok, err)
	}
}
func TestOutageIsCacheMiss(t *testing.T) {
	m := NewMemory(time.Unix(100, 0))
	m.Down = true
	s := New(m)
	var out fixture
	ok, err := s.Get(context.Background(), NamespaceSupport, "session", &out)
	if err != nil || ok {
		t.Fatalf("ok=%v err=%v", ok, err)
	}
}
func TestInvalidation(t *testing.T) {
	m := NewMemory(time.Unix(100, 0))
	s := New(m)
	_ = s.Put(context.Background(), NamespaceRead, "x", fixture{}, ReadTTL)
	if err := s.Invalidate(context.Background(), NamespaceRead, "x"); err != nil {
		t.Fatal(err)
	}
	var out fixture
	ok, _ := s.Get(context.Background(), NamespaceRead, "x", &out)
	if ok {
		t.Fatal("entry survived invalidation")
	}
}

func TestOutageRejectsWritesAndInvalidation(t *testing.T) {
	m := NewMemory(time.Unix(100, 0))
	m.Down = true
	s := New(m)
	if err := s.Put(context.Background(), NamespaceRead, "x", fixture{}, ReadTTL); err != ErrUnavailable {
		t.Fatalf("put err=%v", err)
	}
	if err := s.Invalidate(context.Background(), NamespaceRead, "x"); err != ErrUnavailable {
		t.Fatalf("invalidate err=%v", err)
	}
}
