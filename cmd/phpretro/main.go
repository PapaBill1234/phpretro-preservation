package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/server"
)

func main() {
	port, err := server.PortFromEnv(os.Getenv("PORT"))
	if err != nil {
		log.Fatal(err)
	}
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           server.New(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	log.Printf("phpretro listening on :%s", port)
	log.Fatal(srv.ListenAndServe())
}
